"""Shared pytest fixtures: a temp wardrobe, synthetic items, frozen 'now'.

All fixture data is synthetic - no personal data, ever.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import shutil

import pytest

from wardrobe_capsule.store import Wardrobe

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 31)


@pytest.fixture
def fixtures_path() -> Path:
    return FIXTURES


@pytest.fixture
def now() -> date:
    """Frozen 'today' used to keep tests reproducible; matches fixtures."""
    return TODAY


@pytest.fixture
def sample_wardrobe(tmp_path: Path) -> Wardrobe:
    """A copy of the sample closet, so tests never mutate the fixture file."""
    path = tmp_path / "sample_wardrobe.json"
    shutil.copy(FIXTURES / "sample_wardrobe.json", path)
    return Wardrobe(path)


@pytest.fixture
def empty_wardrobe(tmp_path: Path) -> Wardrobe:
    return Wardrobe(tmp_path / "empty.json")


@pytest.fixture
def fresh_wardrobe(tmp_path: Path) -> Wardrobe:
    return Wardrobe(tmp_path / "wardrobe.json")
