"""Tests for the MCP server: tools and prompts end-to-end with fixtures."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from wardrobe_capsule.store import Wardrobe
from wardrobe_capsule.server import build_server


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def tool_text(result: Any) -> str:
    assert result.is_error is False, result
    return result.content[0].text  # type: ignore[union-attr]


@pytest.fixture
def server(empty_wardrobe: Wardrobe):
    return build_server(empty_wardrobe)


@pytest.fixture
def sample_server(sample_wardrobe: Wardrobe):
    return build_server(sample_wardrobe)


class TestToolListing:
    def test_all_tools_listed(self, server) -> None:
        names = {t.name for t in run(server.list_tools())}
        assert {
            "add_item",
            "list_items",
            "record_wear",
            "suggest_outfit",
            "unworn_report",
            "donate_triage",
            "mark_donated",
            "packing_list",
        } <= names


class TestAddItem:
    def test_adds_and_persists(self, server, empty_wardrobe: Wardrobe) -> None:
        text = tool_text(
            run(
                server.call_tool(
                    "add_item",
                    {"name": "soft cardigan", "category": "tops", "color": "oatmeal"},
                )
            )
        )
        assert "Logged soft cardigan" in text
        saved = json.loads(empty_wardrobe.path.read_text(encoding="utf-8"))
        assert "soft-cardigan" in saved["items"]

    def test_bad_input_reports_gracefully(self, server) -> None:
        text = tool_text(
            run(server.call_tool("add_item", {"name": "hat", "category": "caps"}))
        )
        assert "Could not save that" in text
        assert "caps" in text

    def test_no_category_defaults_to_all_seasons(self, server, empty_wardrobe: Wardrobe) -> None:
        tool_text(
            run(
                server.call_tool(
                    "add_item", {"name": "plain tee", "category": "tops", "seasons": ["all"]}
                )
            )
        )
        item = empty_wardrobe.find_item("plain tee")
        assert item["seasons"] == ["all"]


class TestListItems:
    def test_empty_closet_tone(self, server) -> None:
        text = tool_text(run(server.call_tool("list_items", {})))
        assert "Nothing logged yet" in text
        assert "add_item" in text

    def test_lists_sample_closet(self, sample_server) -> None:
        text = tool_text(run(sample_server.call_tool("list_items", {"category": "tops"})))
        assert "green band shirt" in text
        assert "navy chinos" not in text


class TestRecordWear:
    def test_wear_updates_item(self, sample_server, sample_wardrobe: Wardrobe) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "record_wear", {"item": "green band shirt", "date": "2026-10-31"}
                )
            )
        )
        assert "Counted green band shirt" in text
        item = sample_wardrobe.find_item("green band shirt")
        assert item["last_worn"] == "2026-10-31"
        assert item["times_worn"] == 8

    def test_unknown_item_is_gentle(self, sample_server) -> None:
        text = tool_text(
            run(sample_server.call_tool("record_wear", {"item": "tutu"}))
        )
        assert "Couldn't find 'tutu'" in text


class TestSuggestOutfit:
    def test_suggests_for_temperature(self, sample_server) -> None:
        text = tool_text(
            run(sample_server.call_tool("suggest_outfit", {"temp_c": 26, "occasion": "fancy"}))
        )
        assert "summer" in text
        assert "floral summer dress" in text

    def test_suggests_from_weather_words(self, sample_server) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "suggest_outfit", {"weather_words": "freezing", "occasion": "casual"}
                )
            )
        )
        assert "(-5" in text or "-5" in text
        assert "outerwear" in text

    def test_empty_closet_is_honest_about_gaps(self, server) -> None:
        text = tool_text(
            run(server.call_tool("suggest_outfit", {"temp_c": 18, "occasion": "casual"}))
        )
        assert "add_item" in text
        assert "tops" in text

    def test_bad_occasion_reported(self, sample_server) -> None:
        text = tool_text(
            run(sample_server.call_tool("suggest_outfit", {"temp_c": 18, "occasion": "gala"}))
        )
        assert "Could not suggest" in text and "gala" in text


class TestTriageTools:
    def test_donate_triage_lists_bag(self, sample_server) -> None:
        text = tool_text(run(sample_server.call_tool("donate_triage", {})))
        assert "Donate bag" in text
        assert "never worn" in text

    def test_unworn_report(self, sample_server) -> None:
        text = tool_text(run(sample_server.call_tool("unworn_report", {"days": 90})))
        assert "Unworn watch" in text
        assert "green band shirt" in text

    def test_mark_donated_removes_item(self, sample_server, sample_wardrobe: Wardrobe) -> None:
        text = tool_text(
            run(sample_server.call_tool("mark_donated", {"item": "green band shirt"}))
        )
        assert "donate bag" in text
        assert sample_wardrobe.find_item("green band shirt") is None
        donated = [d["id"] for d in sample_wardrobe.donated()]
        assert "green-band-shirt" in donated


class TestPackingTool:
    def test_packs_a_trip(self, sample_server) -> None:
        text = tool_text(
            run(
                sample_server.call_tool(
                    "packing_list",
                    {"days": 3, "temp_c": 18, "occasions": "casual, work, fancy"},
                )
            )
        )
        assert "Packing list for 3 day(s)" in text
        assert "Day 1" in text and "Day 3" in text

    def test_flags_the_gaps(self, sample_server) -> None:
        text = tool_text(
            run(sample_server.call_tool("packing_list", {"days": 6, "temp_c": 5}))
        )
        assert "Heads up" in text
        assert "re-wear" in text

    def test_gentle_when_closet_is_empty(self, server) -> None:
        text = tool_text(
            run(server.call_tool("packing_list", {"days": 3, "temp_c": 18}))
        )
        assert "log a few basics" in text

    def test_no_weather_is_a_polite_ask(self, sample_server) -> None:
        text = tool_text(run(sample_server.call_tool("packing_list", {"days": 3})))
        assert "temperature" in text or "weather" in text


class TestPrompts:
    def test_get_dressed_today_prompt(self, server) -> None:
        prompts = run(server.list_prompts())
        assert [p.name for p in prompts] == ["get_dressed_today"]
        got = run(server.get_prompt("get_dressed_today", {}))
        text = got.messages[0].content.text  # type: ignore[union-attr]
        assert "suggest_outfit" in text
        assert "Never push" in text or "never push" in text


class TestDefaultPath:
    def test_env_var_overrides(self, tmp_path: Path, monkeypatch) -> None:
        from wardrobe_capsule.server import build_server

        monkeypatch.setenv("WARDROBE_CAPSULE_PATH", str(tmp_path / "env.json"))
        srv = build_server()
        run(srv.call_tool("add_item", {"name": "env tee", "category": "tops"}))
        data = json.loads((tmp_path / "env.json").read_text(encoding="utf-8"))
        assert "env-tee" in data["items"]
