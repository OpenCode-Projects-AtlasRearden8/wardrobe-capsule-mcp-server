# wardrobe-capsule-mcp-server

A calmer closet, one small tool at a time. A local MCP server that gives
an AI assistant a grounded, honest view of the clothes you actually own -
no shopping feeds, no trend pressure, no "philosophy of style" essay.
You log what you have; the server does the boring math.

Built by **Asdale Dynamics, LLC** - low-energy friendly, ADHD-aware, and
strictly local-first: your closet lives in one JSON file on your machine,
and nothing ever leaves it.

## What it does

- **Log clothes you own** with name, category, color, seasons, style
  tags, notes, and a 1-5 *wearability* score (5 = zero effort).
- **Get outfit suggestions** for weather (temperature or words like
  "cool and rainy") and occasion (errands, casual, work, cozy, active,
  fancy). Simple, predictable scoring rules - no mystery.
- **Track what keeps unworn.** An "Unworn watch" quietly lists anything
  not worn in the last 90 days (or never worn at all).
- **Packing lists for trips** built from your real items, with rotation
  across days and honest gap warnings ("3 days usually wants 2 tops; you
  have 1 logged - expect to re-wear").
- **Donate-bag triage by last-worn date.** Sorts the closet into a
  donate bag, keepers, and "your call". Nothing is moved until you
  actively run `mark_donated`.

Three deliberate design choices:

1. **Low-energy friendly.** Every flow works in one-line entries, every
   failure message says what to do next, and nothing nags.
2. **localStorage-style JSON store.** One indented, human-readable
   `wardrobe.json` that you can open in any editor.
3. **Distinct from other tools.** This is not a fashion tracker (no
   brands, sizes, or shopping) and not a craft/WIP tracker (no projects)
   and has nothing to say about health - just clothes and calm.

## Requirements

- Python 3.10+
- The `mcp` package (works with SDK 1.x and 2.x)

## Install

```bash
pip install -e .
```

## Run

```bash
# as an installed command
wardrobe-capsule-server

# or as a module
python -m wardrobe_capsule.server
```

The server speaks MCP over stdio. Point your MCP client at it:

```json
{
  "mcpServers": {
    "wardrobe-capsule": {
      "command": "wardrobe-capsule-server"
    }
  }
}
```

Set `WARDROBE_CAPSULE_PATH` to choose the wardrobe file location
(default: `data/wardrobe.json` next to the package).

## Tools

| Tool | What it does |
| --- | --- |
| `add_item` | Log one piece: name, category, color, seasons, styles, wearability 1-5, optional notes and last-worn date. |
| `list_items` | Show the closet, optionally filtered by category. |
| `record_wear` | Count an item as worn today (or a given date); keeps rotation honest. |
| `suggest_outfit` | Pick an outfit for a temperature (or weather words) and occasion. |
| `unworn_report` | What hasn't been worn in N days (default 90), plus your most-worn item. |
| `donate_triage` | Sort into donate bag / keep / your call by last-worn date (default 180 days). |
| `mark_donated` | Move one item out of the closet into the donate bag (recorded in the file). |
| `packing_list` | Multi-day trip list from your real items, with per-day occasions and gap warnings. |

There is also a `get_dressed_today` prompt: a gentle, low-energy
walkthrough that asks about energy and weather before suggesting one
easy outfit.

## How suggestions work (the boring math)

- Weather picks a season: 24°C+ is summer, under 12°C is winter,
  in between is spring/fall.
- Each item scores: **+3** for season match ("all-season" always
  matches), **+2** for matching the occasion's style, **+0..+5** for
  wearability, and **+1** if it hasn't been worn in 14+ days (a gentle
  rotation nudge). High score wins; ties break by id so results are
  repeatable.
- Fancy occasions prefer a dress when you've logged one; cold snaps add
  outerwear; work and fancy get an accessory if you own one.

The donate rules are equally plain: worn within 180 days -> keep; not
worn in 180+ days -> donate bag; never worn but new (under 90 days) ->
keep; never worn 90+ days -> "your call"; never worn 180+ days ->
donate bag. You make every final call.

## Privacy

- Everything is stored in one JSON file on your machine. No accounts,
  no cloud, no analytics. `data/wardrobe.json` is git-ignored by default
  so your closet never ends up in source control.
- Questions never ask for anything sensitive - colors and seasons are
  plenty.

## Testing

```bash
pip install pytest
pytest
```

The suite covers the suggestion rules (season mapping, scoring, outfit
assembly), donate triage rules, the JSON store, packing rotation and
gap warnings, every MCP tool end-to-end, and a stdio smoke test that
boots the real server and talks MCP to it.

## Project layout

```
src/wardrobe_capsule/
  store.py     # JSON wardrobe store (the "localStorage")
  outfits.py   # season mapping + scoring + outfit assembly
  triage.py    # unworn watch + donate-bag sorting
  packing.py   # trip packing lists from your real items
  server.py    # MCP tools over stdio
tests/
```

## Status

Early and calm. See `STATUS.md` for what works, how it was verified,
and known gaps.

## Credits and license

Built and maintained by **Asdale Dynamics, LLC** as part of its
beginner-friendly, local-first AI tooling. Released under the
[MIT License](LICENSE) - `Copyright (c) 2026 Asdale Dynamics, LLC`.

More from the LLC: [dylanasdale.github.io](https://dylanasdale.github.io)
- AI explained like a friend would: plain English, step by step, never
condescending.
