"""The wardrobe store: one human-readable JSON file, like browser localStorage.

Everything lives on your machine. No accounts, no cloud, no sync.
Structure (localStorage-style dict):

    {
      "format": "wardrobe-capsule/1",
      "items":   { "<id>": {...} },   # everything you own
      "donated": { "<id>": {...} },   # items moved to a donate bag
      "wear_log": [ {"id": ..., "date": "YYYY-MM-DD"} ]
    }

The file is written atomically and indented, so you can open it in any
editor and understand it.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

FORMAT = "wardrobe-capsule/1"

CATEGORIES = ("tops", "bottoms", "dresses", "outerwear", "shoes", "accessories")
SEASONS = ("spring", "summer", "fall", "winter", "all")
STYLES = ("casual", "work", "dressy", "cozy", "active", "home")


class WardrobeError(ValueError):
    """Raised for friendly, fixable problems with wardrobe data."""


def today_str() -> str:
    """Today as YYYY-MM-DD (UTC)."""
    return datetime.now(timezone.utc).date().isoformat()


def parse_date(text: str | None) -> date | None:
    """Parse a YYYY-MM-DD string, or return None for empty/None."""
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise WardrobeError(
            f"'{text}' is not a date I can read. Use YYYY-MM-DD, like 2026-10-31."
        ) from exc


def slugify(text: str) -> str:
    """Lowercase, hyphenated id material from any name string."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "item"


def dash_list(values: list[str] | tuple[str, ...]) -> str:
    """'a, b or c' with a tiny bit of punctuation care."""
    vals = [str(v) for v in values]
    if not vals:
        return ""
    if len(vals) == 1:
        return vals[0]
    return ", ".join(vals[:-1]) + " or " + vals[-1]


class Wardrobe:
    """Read/write access to one wardrobe JSON file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data: dict[str, Any] = self._load()

    # ------------------------------------------------------------------ io

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"format": FORMAT, "items": {}, "donated": {}, "wear_log": []}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise WardrobeError(
                f"Could not read {self.path}: {exc}. "
                "The file should be the wardrobe JSON the server wrote."
            ) from exc
        if not isinstance(raw, dict):
            raise WardrobeError(f"{self.path} is not a wardrobe JSON object.")
        items = raw.get("items")
        if items is None or isinstance(items, list):
            items = {i["id"]: i for i in items or [] if isinstance(i, dict) and "id" in i}
        raw.setdefault("format", FORMAT)
        raw["items"] = items if isinstance(items, dict) else {}
        donated = raw.setdefault("donated", {})
        if not isinstance(donated, dict):
            raw["donated"] = {}
        log = raw.setdefault("wear_log", [])
        if not isinstance(log, list):
            raw["wear_log"] = []
        return raw

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".wardrobe-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(self.data, indent=2, ensure_ascii=False))
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # -------------------------------------------------------------- items

    def items(self) -> list[dict[str, Any]]:
        return list(self.data["items"].values())

    def add_item(
        self,
        name: str,
        category: str,
        color: str = "",
        seasons: str | list[str] | None = None,
        styles: str | list[str] | None = None,
        wearability: int | str = 3,
        notes: str = "",
        last_worn: str | None = None,
        added: str | None = None,
    ) -> dict[str, Any]:
        """Log one piece of clothing. Raises WardrobeError on bad input."""
        name = (name or "").strip()
        if not name:
            raise WardrobeError("Give the item a name, like 'blue cardigan'.")
        category = (category or "").strip().lower()
        if category not in CATEGORIES:
            raise WardrobeError(
                f"'{category or '(none)'}' is not a known category. "
                f"Use one of: {dash_list(CATEGORIES)}."
            )
        season_set = self._normalize_tags(seasons, "seasons", SEASONS, "all")
        style_set = self._normalize_tags(styles, "styles", STYLES, "casual")
        try:
            wear = int(wearability)
        except (TypeError, ValueError) as exc:
            raise WardrobeError("Wearability is a number 1-5.") from exc
        if not 1 <= wear <= 5:
            raise WardrobeError("Wearability is a number 1-5 (5 = easiest to wear).")
        worn_date = parse_date(last_worn)
        added_date = parse_date(added) or date.today()

        base_id = slugify(name)
        item_id = base_id
        n = 2
        while item_id in self.data["items"] or item_id in self.data["donated"]:
            item_id = f"{base_id}-{n}"
            n += 1

        item = {
            "id": item_id,
            "name": name,
            "category": category,
            "color": (color or "").strip().lower(),
            "seasons": season_set,
            "styles": style_set,
            "wearability": wear,
            "notes": (notes or "").strip(),
            "last_worn": worn_date.isoformat() if worn_date else None,
            "times_worn": 1 if worn_date else 0,
            "added": added_date.isoformat(),
        }
        self.data["items"][item_id] = item
        self.save()
        return item

    def _normalize_tags(
        self,
        value: str | list[str] | None,
        label: str,
        allowed: tuple[str, ...],
        default: str,
    ) -> list[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            tags = {default}
        elif isinstance(value, str):
            tags = {t.strip().lower() for t in value.split(",") if t.strip()}
        else:
            tags = {str(t).strip().lower() for t in value}
            # "summer, fall" as one string inside a list
            flat: set[str] = set()
            for t in tags:
                flat.update(part.strip() for part in t.split(",") if part.strip())
            tags = flat
        if "all" in tags and label == "seasons":
            tags = {"all"}
        bad = sorted(t for t in tags if t not in allowed)
        if bad:
            raise WardrobeError(
                f"Unknown {label}: {dash_list(bad)}. Allowed: {dash_list(allowed)}."
            )
        return sorted(tags, key=lambda t: (allowed + (t,)).index(t))

    def find_item(self, query: str) -> dict[str, Any] | None:
        """Match by full id, then by name (case-insensitive substring)."""
        query = (query or "").strip().lower()
        if not query:
            return None
        for item in self.data["items"].values():
            if item["id"] == query:
                return item
        matches = [
            item
            for item in self.data["items"].values()
            if query in item["name"].lower() or query in item["id"]
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    def record_wear(self, item: dict[str, Any], when: str | None = None) -> dict[str, Any]:
        """Mark an item worn on a date (default today) and bump its counts."""
        worn = parse_date(when) or date.today()
        item["last_worn"] = worn.isoformat()
        item["times_worn"] = int(item.get("times_worn", 0) or 0) + 1
        self.data["wear_log"].append({"id": item["id"], "date": worn.isoformat()})
        self.save()
        return item

    def remove_item(
        self,
        item: dict[str, Any],
        reason: str = "donated",
        donated_to: str = "",
    ) -> dict[str, Any]:
        """Move an item out of the closet (default: into the donate bag)."""
        item = dict(item)
        item["removed"] = reason
        item["removed_date"] = today_str()
        if donated_to:
            item["donated_to"] = donated_to
        del self.data["items"][item["id"]]
        self.data["donated"][item["id"]] = item
        self.save()
        return item

    def donated(self) -> list[dict[str, Any]]:
        return list(self.data["donated"].values())

    # -------------------------------------------------------------- views

    def by_category(self, category: str | None = None) -> list[dict[str, Any]]:
        got = [
            i for i in self.items() if not category or i["category"] == category.lower()
        ]
        return sorted(got, key=lambda i: (i["category"], i["name"].lower()))
