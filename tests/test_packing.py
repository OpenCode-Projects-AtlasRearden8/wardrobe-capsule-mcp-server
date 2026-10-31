"""Tests for trip packing-list rules."""

from __future__ import annotations

from datetime import date

from wardrobe_capsule.packing import build_packing_list, gaps_for
from wardrobe_capsule.store import Wardrobe

TODAY = date(2026, 10, 31)


def packing(**over):
    wardrobe = over.pop("wardrobe")
    base = dict(days=3, temp_c=18, weather_words="", occasions=None, today=TODAY)
    base.update(over)
    return build_packing_list(wardrobe, **base)


class TestPacking:
    def test_covers_a_three_day_trip(self, sample_wardrobe: Wardrobe) -> None:
        plan = packing(wardrobe=sample_wardrobe)
        assert len(plan["days"]) == 3
        for n, pieces in plan["days"]:
            roles = {role for role, _ in pieces}
            assert "top" in roles or "dress" in roles
            assert "bottom" in roles or "dress" in roles
            assert "shoes" in roles

    def test_rotates_tops_across_days(self, sample_wardrobe: Wardrobe) -> None:
        plan = packing(wardrobe=sample_wardrobe, days=3)
        tops = [p["id"] for _, pieces in plan["days"] for r, p in pieces if r == "top"]
        assert len(tops) == 3
        # two tops logged for this season, one gets a second turn
        assert set(tops) == {"grey-hoodie", "green-band-shirt"}
        assert tops[0] != tops[1]

    def test_same_item_reused_when_closet_is_thin(self, sample_wardrobe: Wardrobe) -> None:
        plan = packing(wardrobe=sample_wardrobe, days=6)
        assert len(plan["days"]) == 6
        gaps_joined = " ".join(plan["gaps"])
        assert "re-wear" in gaps_joined

    def test_cold_trips_flag_outerwear(self, sample_wardrobe: Wardrobe) -> None:
        plan = packing(wardrobe=sample_wardrobe, days=2, temp_c=5)
        roles_day1 = {r for r, _ in plan["days"][0][1]}
        assert "outerwear" in roles_day1

    def test_gaps_for_empty_closet(self, empty_wardrobe: Wardrobe) -> None:
        gaps = gaps_for(empty_wardrobe, 18, 3)
        assert gaps == ["No items logged yet - log a few basics first and try again."]

    def test_off_season_items_not_packed(self, sample_wardrobe: Wardrobe) -> None:
        plan = packing(wardrobe=sample_wardrobe, days=3, temp_c=28)  # summer
        all_ids = {p["id"] for _, pieces in plan["days"] for _, p in pieces}
        assert "black-blazer" not in all_ids  # fall/winter/spring only
        assert "green-band-shirt" in all_ids  # summer/spring tee is fair game

    def test_weather_words_set_the_packing_season(self, sample_wardrobe: Wardrobe) -> None:
        plan = packing(wardrobe=sample_wardrobe, days=2, temp_c=None, weather_words="cold snowy")
        roles = {r for r, _ in plan["days"][0][1]}
        assert "outerwear" in roles

    def test_no_temp_no_plan(self, sample_wardrobe: Wardrobe) -> None:
        assert packing(wardrobe=sample_wardrobe, temp_c=None, weather_words="") is None

    def test_occasions_per_day(self, sample_wardrobe: Wardrobe) -> None:
        plan = packing(
            wardrobe=sample_wardrobe, days=2, occasions="casual, fancy", temp_c=26
        )
        day1 = dict((r, p["id"]) for r, p in plan["days"][0][1])
        day2 = dict((r, p["id"]) for r, p in plan["days"][1][1])
        assert "dress" not in day1
        assert "dress" in day2  # fancy day uses the dress
