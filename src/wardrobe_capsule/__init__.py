"""wardrobe-capsule-mcp-server: a calmer closet, one small tool at a time.

Local-first, JSON-file backed. Built by Asdale Dynamics, LLC.
"""

from .store import (
    CATEGORIES,
    SEASONS,
    STYLES,
    Wardrobe,
    WardrobeError,
    parse_date,
)
from .outfits import build_outfit, season_for_temp, temps_for_words
from .triage import triage, unworn_report
from .packing import build_packing_list

__all__ = [
    "CATEGORIES",
    "SEASONS",
    "STYLES",
    "Wardrobe",
    "WardrobeError",
    "parse_date",
    "build_outfit",
    "season_for_temp",
    "temps_for_words",
    "triage",
    "unworn_report",
    "build_packing_list",
]
__version__ = "0.1.0"
