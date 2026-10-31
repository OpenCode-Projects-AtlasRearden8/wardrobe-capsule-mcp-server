"""Donate-bag triage and unworn tracking, by last-worn date.

The rules are calm and explainable:

- Never worn, added under 90 days ago  -> "give it a chance"
- Never worn, 90-179 days ago          -> "your call"
- Never worn, 180+ days ago            -> donate bag
- Worn, but not in `min_days` (default 180) -> donate bag
- Worn within `min_days`               -> keep

No guilt, no streak shaming. It's your closet.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .store import Wardrobe, parse_date

NEW_DAYS = 90
DEFAULT_MIN_DAYS = 180


def days_together(item: dict[str, Any], today: date) -> int:
    """Days since the item last (or ever) was worn, judged from 'added'."""
    last = parse_date(item.get("last_worn"))
    if last is not None:
        return max((today - last).days, 0)
    added = parse_date(item.get("added")) or today
    return max((today - added).days, 0)


def triage(
    wardrobe: Wardrobe, min_days: int = DEFAULT_MIN_DAYS, today: date | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Sort owned items into donate / keep / your_call buckets."""
    today = today or date.today()
    result: dict[str, list[dict[str, Any]]] = {"donate": [], "keep": [], "your_call": []}
    for item in wardrobe.items():
        last = parse_date(item.get("last_worn"))
        if last is None:
            if days_together(item, today) >= min_days:
                result["donate"].append(item)
            elif days_together(item, today) >= NEW_DAYS:
                result["your_call"].append(item)
            else:
                result["keep"].append(item)
            continue
        if days_together(item, today) >= min_days:
            result["donate"].append(item)
        else:
            result["keep"].append(item)
    result["donate"].sort(key=lambda i: (-days_together(i, today), i["id"]))
    result["your_call"].sort(key=lambda i: (-days_together(i, today), i["id"]))
    result["keep"].sort(key=lambda i: (i["name"].lower(),))
    return result


def render_triage(buckets: dict[str, list[dict[str, Any]]], min_days: int) -> str:
    """Friendly text of a triage, low-energy friendly."""
    donate = buckets["donate"]
    your_call = buckets["your_call"]
    keep = buckets["keep"]
    lines = []
    if donate:
        lines.append("Donate bag (worn long ago or never):")
        for item in donate:
            note = f"  - {item['name']} ({item['category']}, {item['color'] or 'no color logged'}"
            note += f", {item['styles'][0]}" if item.get("styles") else ""
            note += ")"
            worn_note = "" if item.get("last_worn") else " - never worn"
            lines.append(f"{note}{worn_note}")
        lines.append("That's a bag that frees up real hanger space. One item out is a win.")
    if your_call:
        lines.append("Your call (reasonably new, not worn yet):")
        for item in your_call:
            lines.append(f"  - {item['name']} ({item['category']}) - give it one season")
    if keep:
        lines.append("Keep (worn within " + str(min_days) + " days): " + str(len(keep)) + " item(s)")
    if not lines:
        return "Nothing queued up - your closet is calm today."
    lines.append("")
    lines.append(
        "Remember: this is a nudge, not a rule. Only you know what something is worth."
    )
    return "\n".join(lines)


def unworn_report(
    wardrobe: Wardrobe, days: int = NEW_DAYS, today: date | None = None
) -> dict[str, Any]:
    """Everything not worn in `days`, plus a couple of closet stats."""
    today = today or date.today()
    stale = []
    for item in wardrobe.items():
        if days_together(item, today) > days:
            stale.append(item)
    stale.sort(key=lambda i: (-days_together(i, today), i["id"]))
    total = len(wardrobe.items())
    most = max(wardrobe.items(), key=lambda i: i.get("times_worn", 0), default=None)
    return {
        "unworn": stale,
        "total": total,
        "most_worn": most,
        "days": days,
    }


def render_unworn(report: dict[str, Any]) -> str:
    unworn = report["unworn"]
    head = f"Unworn watch - {len(unworn)} of {report['total']} items not worn in {report['days']} days."
    if not unworn:
        return head + " Everything has been getting wear - nice."
    lines = [head]
    for item in unworn:
        never = "" if item.get("last_worn") else " (never worn)"
        lines.append(f"  - {item['name']} ({item['category']}){never}")
    most = report.get("most_worn")
    if most and most.get("times_worn", 0) > 0:
        lines.append(
            f"  Favourite so far: {most['name']} - worn {most['times_worn']}x."
        )
    return "\n".join(lines)
