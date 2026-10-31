# STATUS - wardrobe-capsule-mcp-server

Date: 2026-10-31
Maintainer: Asdale Dynamics, LLC

## What was built

A local MCP server for a calmer closet. It gives one AI assistant an
honest, grounded picture of the clothes you actually own, and does the
boring math for you:

- **`add_item` / `list_items`** - log and review your real clothes with
  category, color, seasons, style tags, wearability (1-5), notes, and
  optional last-worn dates.
- **`record_wear`** - count an item as worn (today or a given date); it
  updates each item's last-worn date and wear count plus a wear log.
- **`suggest_outfit`** - one outfit for a temperature (or weather words
  like "cool and rainy") and an occasion (errands, casual, work, cozy,
  active, fancy). Plain, documented scoring rules; outerwear added when
  it's cold/snowy/windy; dresses preferred for fancy occasions.
- **`unworn_report`** - the "Unworn watch": anything not worn in N days
  (default 90) or never worn, plus your most-worn item.
- **`donate_triage`** - sorts the closet into a donate bag / keep / your
  call by last-worn date (default 180 days). Nothing moves until you run
  `mark_donated` yourself; donated items are archived in the file.
- **`packing_list`** - multi-day trip lists built from your real items,
  with per-day occasions, top rotation across days, and honest gap
  warnings ("6 days usually wants about 3 tops; you have 1 logged for
  winter - expect to re-wear").
- **`get_dressed_today` prompt** - a gentle, low-energy walkthrough that
  asks about energy and weather before suggesting one easy outfit.

Design constraints honored: low-energy friendly throughout; one
localStorage-style JSON store (`data/wardrobe.json`, indented,
git-ignored, human-editable); no health/medical content of any kind; no
shopping, brands, or trend pressure; everything stays on your machine.

Deliberately distinct from craft-wip-mcp-server (projects vs. clothing)
and from fashion trackers (no feeds, no commerce, no style advice).

## Layout

```
src/wardrobe_capsule/
  store.py     # JSON wardrobe store (localStorage-style, atomic writes)
  outfits.py   # season mapping + scoring + outfit assembly
  triage.py    # unworn watch + donate-bag sorting
  packing.py   # trip packing lists from real items
  server.py    # MCP tools + prompt over stdio (SDK 1.x and 2.x)
tests/         # 77 tests: rules, store, tools, stdio smoke
README.md, LICENSE (MIT), pyproject.toml
```

## How to run

```bash
pip install -e .
wardrobe-capsule-server        # or: python -m wardrobe_capsule.server
```

Point an MCP client at the command (stdio). `WARDROBE_CAPSULE_PATH`
selects the wardrobe file; the CLI replaces `command` in the client --
e.g. `wardrobe-capsule-server`.

## Verification results

- `python3 -m pytest` -> **77 passed** (store, suggestion rules, triage
  rules, packing rules, all MCP tools via the SDK, and a stdio smoke
  test that boots the real server and round-trips MCP calls).
- `python3 -m build --wheel` -> built cleanly
  (`wardrobe_capsule_mcp_server-0.1.0-py3-none-any.whl`).
- Manual stdio check: the `wardrobe-capsule-server` entry point answered
  an MCP `initialize` handshake on stdio (SDK 2.x path).
- `pyflakes` clean across `src/` and `tests/`.
- Fix iterations: item ids are now slug(name) only (color was appended
  by mistake); the `sample_wardrobe` fixture is copied into `tmp_path`
  so tests can never rewrite the fixture file; a tool/file function name
  collision (`unworn_report`) was aliased; the smoke test was fixed for
  SDK 2.x's `.tools` response shape.

## Known gaps

- Occasion→style mapping and season thresholds are simple heuristics;
  a wardrobe with layered or transitional pieces may score oddly.
- No item editing beyond wear/donate (`update_item` is future work);
  fields are editable by hand in the JSON file meanwhile.
- Packing lists don't model rain-specific gear (only a reminder line),
  laundry math, or suitcase-size limits.
- Sizes/brands/material are intentionally out of scope; no import from
  existing closet apps; no export (trivial to add - it's one JSON).
- MCP prompts list only `get_dressed_today`; more guided prompts (e.g.
  "clean out one category today") would fit the tool's spirit.
- English only.

## Verification commands used

```bash
python3 -m pytest -q          # 77 passed
python3 -m build --wheel      # wheel builds
python3 -m pyflakes src tests # clean
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
  | WARDROBE_CAPSULE_PATH=/tmp/opencode/boot.json wardrobe-capsule-server
```
