"""Outfit suggestion rules: plain arithmetic, no AI inside the scoring.

The rules are deliberately boring so you can predict them:

- Weather picks a season: >=24C summer, 12-23.9C spring/fall, <12C winter.
- An item scores points for: matching the season (+3), matching the
  occasion's style (+2), wearability 1-5 (+0..+5), and a gentle rotation
  bonus (+1) if it has not been worn in the last 14 days.
- Highest score wins. Ties break by id so results are repeatable.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .store import Wardrobe, WardrobeError, dash_list, parse_date

OCCASIONS = ("errands", "casual", "work", "cozy", "active", "fancy")

# occasion -> styles that fit it (from STYLES)
OCCASION_STYLES: dict[str, tuple[str, ...]] = {
    "errands": ("casual", "home", "work"),
    "casual": ("casual", "home", "cozy"),
    "work": ("work", "casual"),
    "cozy": ("cozy", "casual", "home"),
    "active": ("active", "casual"),
    "fancy": ("dressy", "work"),
}

# weather words -> (temp_c, condition)
WORD_WEATHER: dict[str, tuple[float | None, str | None]] = {
    "hot": (32.0, None),
    "warm": (26.0, None),
    "mild": (18.0, None),
    "pleasant": (20.0, None),
    "cool": (12.0, None),
    "chilly": (8.0, None),
    "cold": (2.0, None),
    "freezing": (-5.0, None),
    "snowy": (-2.0, "snow"),
    "snow": (-2.0, "snow"),
    "rainy": (16.0, "rain"),
    "rain": (16.0, "rain"),
    "drizzly": (14.0, "rain"),
    "humid": (27.0, None),
    "windy": (15.0, "wind"),
}


def season_for_temp(temp_c: float) -> str:
    """Map a temperature to wardrobe seasons (12-23.9 is shoulder season)."""
    if temp_c >= 24.0:
        return "summer"
    if temp_c < 12.0:
        return "winter"
    return "spring"


def season_matches(item: dict[str, Any], season: str) -> bool:
    seasons = item.get("seasons", [])
    return "all" in seasons or season in seasons


def temps_for_words(weather_words: str) -> tuple[float | None, str | None]:
    """Parse freeform weather into (temp_c, condition).

    Later words win so 'cool and rainy' keeps the rain condition.
    """
    temp: float | None = None
    condition: str | None = None
    for word in str(weather_words or "").lower().split():
        if word in WORD_WEATHER:
            w_temp, w_cond = WORD_WEATHER[word]
            if w_temp is not None:
                temp = w_temp
            if w_cond is not None:
                condition = w_cond
    return temp, condition


def resolve_temp(temp_c: float | None, weather_words: str) -> float | None:
    """Explicit temp wins; otherwise read it out of weather words."""
    if temp_c is not None:
        return float(temp_c)
    return temps_for_words(weather_words)[0]


def style_prefs(occasion: str) -> tuple[str, ...]:
    """Styles that suit an occasion ('casual' by default)."""
    return OCCASION_STYLES.get(occasion, OCCASION_STYLES["casual"])


def score_item(
    item: dict[str, Any],
    season: str,
    occasion: str,
    today: date,
    condition: str | None = None,
) -> int:
    """Score one item for today's season and occasion."""
    points = 0
    if season_matches(item, season):
        points += 3
    if set(item.get("styles", [])) & set(style_prefs(occasion)):
        points += 2
    points += int(item.get("wearability", 3))
    last_worn = parse_date(item.get("last_worn"))
    if last_worn is None or (today - last_worn).days >= 14:
        points += 1  # gentle rotation bonus
    if condition == "rain" and item.get("category") == "shoes":
        pass  # shoes are shoes; keep scoring calm and simple
    return points


def cold_enough(temp_c: float | None, condition: str | None) -> bool:
    """Outerwear weather? Cold temps, snow, or strong wind say yes."""
    if condition in ("snow", "wind"):
        return True
    return temp_c is not None and temp_c < 16.0


def _ranked(
    pool: list[dict[str, Any]], season: str, occasion: str, today: date
) -> list[dict[str, Any]]:
    return sorted(
        pool,
        key=lambda item: (-score_item(item, season, occasion, today), item["id"]),
    )


def build_outfit(
    wardrobe: Wardrobe,
    temp_c: float | None,
    occasion: str = "casual",
    today: date | None = None,
    condition: str | None = None,
) -> dict[str, Any] | None:
    """Pick one outfit from the real items, or explain what's missing.

    Returns {"pieces": [(role, item)], "missing": [...], "season": ...}
    or None if a required piece is impossible.
    """
    today = today or date.today()
    if temp_c is None:
        raise WardrobeError("Tell me the temperature or some weather words.")
    if occasion not in OCCASIONS:
        raise WardrobeError(
            f"'{occasion}' is not an occasion I know. Try one of: {dash_list(OCCASIONS)}."
        )
    season = season_for_temp(temp_c)
    pooled: dict[str, list[dict[str, Any]]] = {
        cat: [] for cat in ("tops", "bottoms", "dresses", "shoes", "outerwear", "accessories")
    }
    for item in wardrobe.items():
        cat = item["category"]
        if cat in pooled:
            pooled[cat].append(item)

    ranked = {cat: _ranked(v, season, occasion, today) for cat, v in pooled.items()}
    missing = []
    for cat, pool in ranked.items():
        if cat != "accessories" and not pool:
            missing.append(cat)

    if missing:
        return {"pieces": [], "missing": missing, "season": season}

    dress = ranked["dresses"][0]
    use_dress = occasion == "fancy" and dress is not None
    pieces: list[tuple[str, dict[str, Any]]] = []
    if use_dress:
        pieces.append(("dress", dress))
    else:
        pieces.append(("top", ranked["tops"][0]))
        pieces.append(("bottom", ranked["bottoms"][0]))
    pieces.append(("shoes", ranked["shoes"][0]))
    if cold_enough(temp_c, condition) and ranked["outerwear"]:
        pieces.append(("outerwear", ranked["outerwear"][0]))
    if ranked["accessories"] and occasion in ("fancy", "work"):
        pieces.append(("accessory", ranked["accessories"][0]))
    return {"pieces": pieces, "missing": [], "season": season}
