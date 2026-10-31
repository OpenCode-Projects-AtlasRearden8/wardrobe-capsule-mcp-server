"""Tests for the outfit suggestion rules (season mapping, scoring, dressing).

These are the core "boring arithmetic" rules the README documents.
"""

from __future__ import annotations

from datetime import date

import pytest

from wardrobe_capsule.outfits import (
    build_outfit,
    cold_enough,
    resolve_temp,
    score_item,
    season_for_temp,
    style_prefs,
    temps_for_words,
)
from wardrobe_capsule.store import Wardrobe, WardrobeError

TODAY = date(2026, 10, 31)


def make_item(resource, **over):
    defaults = dict(
        id="item",
        name="item",
        category="tops",
        color="grey",
        seasons=["all"],
        styles=["casual"],
        wearability=3,
        notes="",
        last_worn=None,
        times_worn=0,
        added="2026-10-01",
    )
    defaults.update(over)
    if not hasattr(resource, "data"):  # plain dict item for score tests
        return defaults
    resource.data["items"][defaults["id"]] = defaults
    return defaults


class TestWeatherToSeason:
    def test_hot_weather_is_summer(self) -> None:
        assert season_for_temp(30) == "summer"
        assert season_for_temp(24) == "summer"

    def test_shoulder_season_between_12_and_24(self) -> None:
        assert season_for_temp(20) == "spring"
        assert season_for_temp(12) == "spring"

    def test_cold_weather_is_winter(self) -> None:
        assert season_for_temp(5) == "winter"
        assert season_for_temp(-10) == "winter"

    def test_words_map_to_temps(self) -> None:
        assert temps_for_words("hot")[0] == 32.0
        assert temps_for_words("cool and rainy") == (16.0, "rain")
        assert temps_for_words("cold snowy day") == (-2.0, "snow")
        assert temps_for_words("nothing useful") == (None, None)

    def test_explicit_temp_wins_over_words(self) -> None:
        assert resolve_temp(15, "freezing") == 15.0
        assert resolve_temp(None, "warm") == 26.0

    def test_style_prefs_cover_occasion(self) -> None:
        assert "work" in style_prefs("work")
        assert "dressy" in style_prefs("fancy")


class TestScoring:
    def test_season_match_scores(self) -> None:
        summer_item = make_item({}, seasons=["summer"])
        winter_item = make_item({}, seasons=["winter"])
        hot = TODAY
        assert score_item(summer_item, "summer", "casual", hot) > score_item(
            winter_item, "summer", "casual", hot
        )

    def test_all_season_items_match_everywhere(self) -> None:
        plain = make_item({}, seasons=["all"])
        offseason = make_item({}, seasons=["winter"])
        # all-season always matches; a winter piece gets the +3 instead
        assert score_item(plain, "summer", "casual", TODAY) == score_item(
            offseason, "summer", "casual", TODAY
        ) + 3

    def test_occasion_style_match_scores(self) -> None:
        fancy = make_item({}, styles=["dressy"])
        sloppy = make_item({}, styles=["home"])
        assert score_item(fancy, "summer", "fancy", TODAY) > score_item(
            sloppy, "summer", "fancy", TODAY
        )

    def test_wearability_adds_points(self) -> None:
        easy = make_item({}, wearability=5)
        itchy = make_item({}, wearability=1)
        assert score_item(easy, "summer", "casual", TODAY) > score_item(
            itchy, "summer", "casual", TODAY
        )

    def test_unworn_items_get_rotation_bonus(self) -> None:
        neglected = make_item({}, last_worn="2026-06-01")
        recent = make_item({}, last_worn="2026-10-30")
        assert score_item(neglected, "summer", "casual", TODAY) == score_item(
            recent, "summer", "casual", TODAY
        ) + 1


class TestBuildOutfit:
    def test_full_casual_outfit_picks_pieces(self, sample_wardrobe: Wardrobe) -> None:
        plan = build_outfit(sample_wardrobe, 18, "casual", TODAY)
        assert plan is not None and not plan["missing"]
        roles = {role for role, _ in plan["pieces"]}
        assert {"top", "bottom", "shoes"} <= roles

    def test_cold_weather_adds_outerwear(self, sample_wardrobe: Wardrobe) -> None:
        assert cold_enough(5, None) is True
        assert cold_enough(20, None) is False
        assert cold_enough(20, "snow") is True
        plan = build_outfit(sample_wardrobe, 5, "casual", TODAY)
        roles = {role for role, _ in plan["pieces"]}
        assert "outerwear" in roles

    def test_fancy_prefers_the_dress(self, sample_wardrobe: Wardrobe) -> None:
        plan = build_outfit(sample_wardrobe, 26, "fancy", TODAY)
        roles = {role for role, _ in plan["pieces"]}
        assert "dress" in roles
        assert "top" not in roles and "bottom" not in roles

    def test_fancy_adds_the_dressy_watch(self, sample_wardrobe: Wardrobe) -> None:
        plan = build_outfit(sample_wardrobe, 26, "fancy", TODAY)
        accessories = [p for role, p in plan["pieces"] if role == "accessory"]
        assert accessories == [sample_wardrobe.find_item("fancy silver watch")]

    def test_missing_pieces_explained(self, empty_wardrobe: Wardrobe) -> None:
        plan = build_outfit(empty_wardrobe, 18, "casual", TODAY)
        assert set(plan["missing"]) == {"tops", "bottoms", "dresses", "shoes", "outerwear"}
        assert plan["pieces"] == []

    def test_result_deterministic(self, sample_wardrobe: Wardrobe) -> None:
        a = build_outfit(sample_wardrobe, 18, "casual", TODAY)
        b = build_outfit(sample_wardrobe, 18, "casual", TODAY)
        assert [(r, i["id"]) for r, i in a["pieces"]] == [
            (r, i["id"]) for r, i in b["pieces"]
        ]

    def test_bad_occasion_rejected(self, sample_wardrobe: Wardrobe) -> None:
        with pytest.raises(WardrobeError):
            build_outfit(sample_wardrobe, 18, "gala", TODAY)
