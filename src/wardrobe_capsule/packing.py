"""Trip packing lists built from the real items you logged.

Capacity math is honest but gentle: if the closet can't cover the trip,
the tool says what's thin instead of inventing clothes you don't own.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .store import Wardrobe
from .outfits import (
    OCCASIONS,
    cold_enough,
    resolve_temp,
    score_item,
    season_matches,
    season_for_temp,
    temps_for_words,
)


def _ranked(pool: list[dict[str, Any]], season, occasion, today) -> list[dict[str, Any]]:
    return sorted(
        pool,
        key=lambda item: (-score_item(item, season, occasion, today), item["id"]),
    )


def gaps_for(wardrobe: Wardrobe, temp_c: float, days: int) -> list[str] | None:
    """Warn about holes: nothing logged for the season, or too few to rotate."""
    items = wardrobe.items()
    if not items:
        return ["No items logged yet - log a few basics first and try again."]
    season = season_for_temp(temp_c)
    have = {}
    for cat in ("tops", "bottoms", "dresses", "shoes", "outerwear"):
        have[cat] = [
            i for i in items if i["category"] == cat and season_matches(i, season)
        ]
    if not (have["tops"] and have["bottoms"] and have["shoes"]):
        if have["dresses"]:
            pass  # a dress can cover several days on its own
        elif not (have["tops"] or have["bottoms"]):
            return [f"Nothing in the closet is logged for {season} yet."]
    wanted = {"tops": max(2, (days + 1) // 2), "bottoms": max(1, (days + 2) // 3), "shoes": 1}
    thin = []
    for cat, need in wanted.items():
        got = len(have[cat])
        if got < need:
            thin.append(
                f"{days} days usually wants about {need} {cat}; "
                f"you have {got} logged for {season} - expect to re-wear."
            )
    if cold_enough(temp_c, None) and not have["outerwear"]:
        thin.append(f"Cold trip and no {season} outerwear logged - pack a coat from real life.")
    return thin or None


def build_packing_list(
    wardrobe: Wardrobe,
    days: int,
    temp_c: float | None = None,
    weather_words: str = "",
    occasions: str | list[str] | None = None,
    today: date | None = None,
) -> dict[str, Any] | None:
    """Multi-day packing plan with rotation across days.

    occasions is a comma string or list, one per day (cycled if shorter
    than `days`). Returns {"days": [(n, [(role, item)])], "gaps": [...]}.
    """
    today = today or date.today()
    temp = resolve_temp(temp_c, weather_words)
    _, condition = temps_for_words(weather_words)
    if temp is None:
        return None
    if days < 1:
        days = 1
    if not wardrobe.items():
        return {
            "days": [],
            "gaps": ["No items logged yet - log a few basics first and try again."],
        }
    season = season_for_temp(temp)

    day_occasions: list[str] = []
    if isinstance(occasions, str):
        parts = [p.strip().lower() for p in occasions.split(",") if p.strip()]
    else:
        parts = [str(o).strip().lower() for o in (occasions or [])]
    for p in parts:
        day_occasions.append(p if p in OCCASIONS else "casual")
    while len(day_occasions) < days:
        day_occasions.append(day_occasions[-1] if day_occasions else "casual")
    day_occasions = day_occasions[:days]

    pools: dict[str, list[dict[str, Any]]] = {}
    for cat in ("tops", "bottoms", "dresses", "shoes", "outerwear"):
        pools[cat] = [
            i
            for i in wardrobe.items()
            if i["category"] == cat and season_matches(i, season)
        ]
    ranked = {
        cat: _ranked(pool, season, "casual", today) for cat, pool in pools.items()
    }

    usage: dict[str, int] = {}
    by_usage: dict[str, dict[str, Any]] = {}

    def pick(cat: str, day_index: int) -> dict[str, Any] | None:
        pool = ranked[cat]
        if not pool:
            return None
        # rotate: prefer least-worn-on-this-trip, keep score order as tiebreak
        ordered = sorted(
            pool,
            key=lambda i: (usage.get(i["id"], 0), pool.index(i))
        )
        chosen = ordered[0]
        usage[chosen["id"]] = usage.get(chosen["id"], 0) + 1
        by_usage[chosen["id"]] = chosen
        return chosen

    plan: list[tuple[int, list[tuple[str, dict[str, Any]]]]] = []
    for n, occasion in enumerate(day_occasions, start=1):
        pieces: list[tuple[str, dict[str, Any]]] = []
        dress_pool = ranked["dresses"]
        use_dress = (
            dress_pool
            and (occasion == "fancy" or (usage.get(dress_pool[0]["id"], 0) == 0 and n % 3 == 0))
        )
        if use_dress:
            pieces.append(("dress", pick("dresses", n)))
        else:
            pieces.append(("top", pick("tops", n)))
            pieces.append(("bottom", pick("bottoms", n)))
        pieces.append(("shoes", pick("shoes", n)))
        if cold_enough(temp, condition):
            pieces.append(("outerwear", pick("outerwear", n)))
        pieces = [(role, item) for role, item in pieces if item is not None]
        plan.append((n, pieces))

    gaps = gaps_for(wardrobe, temp, days) or []
    if condition == "rain":
        gaps.append("Rain in the forecast - take the rain shell you own, this list can't see it.")
    return {"days": plan, "gaps": gaps, "season": season}
