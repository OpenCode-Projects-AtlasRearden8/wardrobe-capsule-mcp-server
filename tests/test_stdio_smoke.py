"""Stdio smoke test: boot the real server as a subprocess and talk MCP to it.

Uses the official `mcp` client against a throwaway wardrobe JSON file.
Skipped cleanly if the client pieces are unavailable in the installed SDK.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp.client")

from mcp.client import Client, stdio  # noqa: E402


@pytest.fixture
def stdio_setup(tmp_path: Path):
    log_path = tmp_path / "smoke.json"
    params = stdio.StdioServerParameters(
        command=sys.executable,
        args=["-m", "wardrobe_capsule.server"],
        env={**os.environ, "WARDROBE_CAPSULE_PATH": str(log_path)},
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    return params, log_path


def test_stdio_roundtrip(stdio_setup) -> None:
    params, log_path = stdio_setup

    async def main() -> str:
        async with Client(params) as client:
            listing = await client.list_tools()
            tools = listing.tools  # SDK 2.x model; also fine to read .tools in 1.x
            names = {t.name for t in tools}
            assert {
                "add_item",
                "list_items",
                "record_wear",
                "suggest_outfit",
                "donate_triage",
                "mark_donated",
                "packing_list",
            } <= names
            added = await client.call_tool(
                "add_item",
                {
                    "name": "smoke test tee",
                    "category": "tops",
                    "color": "grey",
                    "seasons": "all",
                    "wearability": 4,
                },
            )
            await client.call_tool("list_items", {})
            await client.call_tool(
                "suggest_outfit", {"temp_c": 18, "occasion": "casual"}
            )
            await client.call_tool("record_wear", {"item": "smoke test tee"})
            await client.call_tool("donate_triage", {})
            packed = await client.call_tool(
                "packing_list", {"days": 2, "temp_c": 18}
            )
        return added.content[0].text + "\n" + packed.content[0].text

    text = asyncio.run(main())
    assert "Logged smoke test tee" in text
    assert "Packing list for 2 day(s)" in text
    data = json.loads(log_path.read_text(encoding="utf-8"))
    assert "smoke-test-tee" in data["items"]
    assert data["items"]["smoke-test-tee"]["times_worn"] == 1
