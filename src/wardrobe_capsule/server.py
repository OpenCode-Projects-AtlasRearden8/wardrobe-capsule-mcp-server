"""MCP server exposing the wardrobe over stdio.

Works with `mcp` 1.x (FastMCP) and 2.x (MCPServer). Run with:

    python -m wardrobe_capsule.server

Local-first, JSON-file backed, low-energy friendly. Not a fashion
tracker, not a shopping feed - just your real clothes, calmly organized.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .outfits import OCCASIONS, build_outfit, resolve_temp, season_for_temp
from .packing import build_packing_list
from .store import (
    Wardrobe,
    WardrobeError,
    dash_list,
    parse_date,
)
from .triage import (
    DEFAULT_MIN_DAYS,
    NEW_DAYS,
    render_triage,
    render_unworn,
    triage,
    unworn_report as unworn_watch,
)

try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCP  # type: ignore

    _MCP_VERSION = "1.x"
except ImportError:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _MCP  # type: ignore

    _MCP_VERSION = "2.x"


def _default_path() -> Path:
    raw = os.environ.get("WARDROBE_CAPSULE_PATH")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent / "data" / "wardrobe.json"


def build_server(wardrobe: Wardrobe | None = None):
    """Create the MCP server bound to a wardrobe (default path from env)."""
    wardrobe = wardrobe or Wardrobe(_default_path())
    server = _MCP(
        "wardrobe-capsule",
        title="Wardrobe Capsule",
        description=(
            "Local closet helper: log your real clothes with color, season and "
            "wearability, get outfit ideas for weather and occasion, watch what "
            "stays unworn, build trip packing lists, and triage a donate bag. "
            "Low-energy friendly - small steps count."
        ),
    )

    @server.tool()
    def add_item(
        name: str,
        category: str,
        color: str = "",
        seasons: str | list[str] | None = "all",
        styles: str | list[str] | None = "casual",
        wearability: int = 3,
        notes: str = "",
        last_worn: str | None = None,
    ) -> str:
        """Log one piece of clothing you own.

        category: tops, bottoms, dresses, outerwear, shoes or accessories.
        seasons: e.g. "all", "summer", "summer, spring".
        styles: casual, work, dressy, cozy, active or home.
        wearability: 1-5, how easy it is to throw on (5 = zero effort).
        last_worn: optional YYYY-MM-DD if you happened to note it.
        """
        try:
            item = wardrobe.add_item(
                name, category, color, seasons, styles, wearability, notes, last_worn
            )
        except WardrobeError as exc:
            return f"Could not save that: {exc}"
        worn = f", last worn {item['last_worn']}" if item["last_worn"] else ""
        return (
            f"Logged {item['name']} ({item['category']}, {item['color'] or 'no color'}, "
            f"{'/'.join(item['seasons'])}, wearability {item['wearability']}/5{worn}). "
            "Your closet inventory just grew by one."
        )

    @server.tool()
    def list_items(category: str | None = None) -> str:
        """Show what's in the closet (optionally one category)."""
        try:
            rows = wardrobe.by_category(category)
        except WardrobeError as exc:
            return f"Could not list: {exc}"
        if not rows:
            base = f"No {category} logged yet." if category else "Nothing logged yet."
            return f"{base} Start small with add_item - even one entry helps."
        lines = [
            f"  {i['name']:<28} {i['category']:<11} {i['color'] or '-':<10} "
            f"{'/'.join(i['seasons']):<13} wear {i['wearability']}/5"
            for i in rows
        ]
        return "\n".join(["Closet (" + str(len(rows)) + " items)"] + lines)

    @server.tool()
    def record_wear(item: str, date: str | None = None) -> str:
        """Mark an item as worn today (or a YYYY-MM-DD date)."""
        found = wardrobe.find_item(item)
        if found is None:
            return (
                f"Couldn't find '{item}'. Check list_items for the exact name - "
                "no pressure, you can just type it again later."
            )
        try:
            parse_date(date)
            updated = wardrobe.record_wear(found, date)
        except WardrobeError as exc:
            return f"Could not record that: {exc}"
        return (
            f"Counted {updated['name']} as worn on {updated['last_worn']} "
            f"({updated['times_worn']} wears logged so far)."
        )

    @server.tool()
    def suggest_outfit(
        temp_c: float | None = None,
        weather_words: str = "",
        occasion: str = "casual",
    ) -> str:
        """Suggest one outfit for today's weather and occasion.

        Give a temperature in Celsius, or words like 'cool and rainy',
        or both. Occasions: errands, casual, work, cozy, active, fancy.
        """
        try:
            temp = resolve_temp(temp_c, weather_words)
            plan = build_outfit(wardrobe, temp, occasion)
        except WardrobeError as exc:
            return f"Could not suggest an outfit: {exc}"
        if plan.get("missing"):
            return (
                "Not enough logged to build an outfit - add a few pieces with "
                "add_item (whenever you have the energy). Missing for "
                f"{occasion}: {dash_list(plan['missing'])}."
            )
        temp = resolve_temp(temp_c, weather_words)
        season = season_for_temp(temp)
        lines = [f"Outfit idea for {int(temp)}C ({season}, {occasion}):"]
        for role, piece in plan["pieces"]:
            lines.append(
                f"  {role:<11} {piece['name']} ({piece['color'] or '-'}, wear "
                f"{piece['wearability']}/5)"
            )
        return "\n".join(lines) + "\nChosen by simple score rules - you know your clothes best."

    @server.tool()
    def unworn_report(days: int = NEW_DAYS) -> str:
        """What hasn't been worn lately (default: last 90 days)."""
        try:
            report = unworn_watch(wardrobe, days)
        except WardrobeError as exc:
            return f"Could not build the report: {exc}"
        return render_unworn(report)

    @server.tool()
    def donate_triage(min_days: int = DEFAULT_MIN_DAYS) -> str:
        """Sort the closet into a donate bag and keepers by last-worn date.

        Nothing is moved - read the list first, act only when you're ready.
        """
        try:
            buckets = triage(wardrobe, min_days)
        except WardrobeError as exc:
            return f"Could not run triage: {exc}"
        return render_triage(buckets, min_days)

    @server.tool()
    def mark_donated(item: str, donated_to: str = "") -> str:
        """Move one item out of the closet into the donate bag."""
        found = wardrobe.find_item(item)
        if found is None:
            return (
                f"Couldn't find '{item}'. Check list_items for the exact name - "
                "and only when you've actually bagged it."
            )
        donated_to_note = f"; donated_to: {donated_to}" if donated_to else ""
        moved = wardrobe.remove_item(found, "donated", donated_to)
        return (
            f"{moved['name']} is out of the closet and into the donate bag"
            f"{donated_to_note}. That's {len(wardrobe.data['donated'])} item(s) moved on."
        )

    @server.tool()
    def packing_list(
        days: int,
        temp_c: float | None = None,
        weather_words: str = "",
        occasions: str | None = None,
    ) -> str:
        """A trip packing list from your real items.

        days is trip length (>=1), temp_c the average temperature (or
        weather_words like 'cool and rainy'), occasions a comma list per
        day (default casual, e.g. 'casual, work, fancy').
        """
        try:
            plan = build_packing_list(wardrobe, days, temp_c, weather_words, occasions)
        except WardrobeError as exc:
            return f"Could not build the packing list: {exc}"
        if plan is None:
            return "Tell me the temperature or some weather words and I'll pack for it."
        if not plan["days"]:
            return " Closet too thin to plan yet" + str(plan["gaps"]) if plan["gaps"] else "Closet empty - log a few basics first."
        out = [f"Packing list for {days} day(s), around {int(resolve_temp(temp_c, weather_words))}C:"]
        for n, pieces in plan["days"]:
            day_items = ", ".join(f"{piece['name']} ({role})" for role, piece in pieces)
            out.append(f"  Day {n}: [ ] {day_items}")
        if plan["gaps"]:
            out.append("Heads up (this list only knows what you logged):")
            out.extend(f"  - {g}" for g in plan["gaps"])
        return "\n".join(out)

    @server.prompt()
    def get_dressed_today() -> str:
        """A gentle, low-energy walk through getting dressed."""
        return (
            "Help me get dressed today, gently.\n"
            "1. Ask how I'm doing for energy - one word is fine.\n"
            "2. Ask the weather or temperature in Celsius.\n"
            "3. Call the suggest_outfit tool with that weather and occasion "
            f"(occasions: {dash_list(OCCASIONS)}).\n"
            "4. Present the outfit as an easy choice, not homework. If I "
            "mention wearing something, offer to log it with record_wear.\n"
            "5. Never push trends, shopping, or guilt. One clean outfit counts."
        )

    return server


def main() -> None:
    server = build_server()
    print(
        f"wardrobe-capsule MCP server ({_MCP_VERSION}) starting on stdio... "
        "json closet, your machine only",
        file=sys.stderr,
    )
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
