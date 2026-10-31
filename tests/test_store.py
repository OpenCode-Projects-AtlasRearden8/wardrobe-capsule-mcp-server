"""Tests for the JSON wardrobe store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wardrobe_capsule.store import Wardrobe, WardrobeError


class TestBasics:
    def test_add_and_read_back(self, fresh_wardrobe: Wardrobe) -> None:
        item = fresh_wardrobe.add_item("Blue flannel", "tops", "blue", "fall, winter")
        assert item["id"] == "blue-flannel"
        assert item["seasons"] == ["fall", "winter"]  # kept in canonical order
        assert fresh_wardrobe.find_item("blue flannel") is not None
        assert fresh_wardrobe.by_category("tops") == [item]

    def test_json_on_disk_is_the_store(self, fresh_wardrobe: Wardrobe) -> None:
        fresh_wardrobe.add_item("Red cap", "accessories", "red")
        raw = json.loads(fresh_wardrobe.path.read_text(encoding="utf-8"))
        assert raw["format"] == "wardrobe-capsule/1"
        assert "red-cap" in raw["items"]
        assert list(raw.keys()) == ["format", "items", "donated", "wear_log"]

    def test_duplicate_names_get_unique_ids(self, fresh_wardrobe: Wardrobe) -> None:
        first = fresh_wardrobe.add_item("Black tee", "tops", "black")
        second = fresh_wardrobe.add_item("Black tee", "tops", "grey")
        assert first["id"] != second["id"]

    def test_seasons_list_with_comma_string(self, fresh_wardrobe: Wardrobe) -> None:
        item = fresh_wardrobe.add_item("Linen shirt", "tops", "white", ["summer, spring"])
        assert item["seasons"] == ["spring", "summer"]


class TestValidation:
    def test_empty_name_rejected(self, fresh_wardrobe: Wardrobe) -> None:
        with pytest.raises(WardrobeError) as err:
            fresh_wardrobe.add_item("  ", "tops")
        assert "name" in str(err.value).lower()

    def test_bad_category_rejected(self, fresh_wardrobe: Wardrobe) -> None:
        with pytest.raises(WardrobeError) as err:
            fresh_wardrobe.add_item("Mystery item", "socks-?", "grey")
        assert "category" in str(err.value)

    def test_bad_season_rejected(self, fresh_wardrobe: Wardrobe) -> None:
        with pytest.raises(WardrobeError) as err:
            fresh_wardrobe.add_item("Sweater", "tops", "green", "monsoon")
        assert "seasons" in str(err.value)

    def test_wearability_range(self, fresh_wardrobe: Wardrobe) -> None:
        with pytest.raises(WardrobeError):
            fresh_wardrobe.add_item("Scratchy suit", "tops", "grey", wearability=9)
        with pytest.raises(WardrobeError):
            fresh_wardrobe.add_item("Scratchy suit", "tops", "grey", wearability=0)

    def test_bad_date_rejected(self, fresh_wardrobe: Wardrobe) -> None:
        with pytest.raises(WardrobeError):
            fresh_wardrobe.add_item("Sweater", "tops", "green", last_worn="oct 4")


class TestFindAndWear:
    def test_find_by_id_then_name(self, sample_wardrobe: Wardrobe) -> None:
        assert sample_wardrobe.find_item("navy-chinos")["id"] == "navy-chinos"
        assert sample_wardrobe.find_item("CHINOS")["id"] == "navy-chinos"
        assert sample_wardrobe.find_item("chino")["id"] == "navy-chinos"
        assert sample_wardrobe.find_item("nope") is None

    def test_record_wear_bumps_counts(self, sample_wardrobe: Wardrobe, tmp_path) -> None:
        item = sample_wardrobe.find_item("navy chinos")
        before = item["times_worn"]
        updated = sample_wardrobe.record_wear(item, "2026-10-31")
        assert updated["last_worn"] == "2026-10-31"
        assert updated["times_worn"] == before + 1
        log = json.loads(sample_wardrobe.path.read_text(encoding="utf-8"))["wear_log"]
        assert log[-1] == {"id": "navy-chinos", "date": "2026-10-31"}

    def test_remove_item_moves_to_donated(self, sample_wardrobe: Wardrobe) -> None:
        item = sample_wardrobe.find_item("navy chinos")
        moved = sample_wardrobe.remove_item(item, donated_to="corner thrift")
        assert moved["donated_to"] == "corner thrift"
        assert sample_wardrobe.find_item("navy chinos") is None
        assert [d["id"] for d in sample_wardrobe.donated()] == [
            "old-college-tee",
            "navy-chinos",
        ]
        assert sample_wardrobe.find_item("navy chinos") is None


class TestRobustLoad:
    def test_legacy_list_items_upgraded(self, tmp_path: Path) -> None:
        path = tmp_path / "legacy.json"
        path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "id": "old-shorts",
                            "name": "old shorts",
                            "category": "bottoms",
                            "wearability": 3,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        book = Wardrobe(path)
        assert book.find_item("old-shorts") is not None
        assert book.data["donated"] == {}
        assert book.data["wear_log"] == []

    def test_corrupt_file_raises_friendly(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(WardrobeError) as err:
            Wardrobe(path)
        assert "Could not read" in str(err.value)

    def test_missing_keys_backfilled(self, tmp_path: Path) -> None:
        path = tmp_path / "sparse.json"
        path.write_text("{}", encoding="utf-8")
        book = Wardrobe(path)
        assert book.items() == []
        book.add_item("Plain tee", "tops", "white")
        assert book.find_item("plain-tee") is not None
