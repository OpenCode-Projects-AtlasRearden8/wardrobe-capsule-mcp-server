"""Tests for donate-bag triage and unworn tracking rules."""

from datetime import date

from wardrobe_capsule.triage import NEW_DAYS, days_together, render_triage, triage, unworn_report
from wardrobe_capsule.store import Wardrobe

TODAY = date(2026, 10, 31)


class TestDaysTogether:
    def test_from_last_worn(self) -> None:
        item = {"last_worn": "2026-10-01", "added": "2026-01-01"}
        assert days_together(item, TODAY) == 30

    def test_never_worn_falls_back_to_added(self) -> None:
        item = {"last_worn": None, "added": "2026-04-02"}
        assert days_together(item, TODAY) == 212


def add(wardrobe: Wardrobe, **over):
    base = dict(
        name="thing",
        category="tops",
        color="grey",
        seasons="all",
        styles="casual",
        wearability=3,
        added="2026-10-01",
    )
    base.update(over)
    return wardrobe.add_item(**base)


class TestTriageRules:
    def test_recently_worn_items_are_kept(self, fresh_wardrobe: Wardrobe) -> None:
        add(fresh_wardrobe, name="worn yesterday", last_worn="2026-10-30")
        buckets = triage(fresh_wardrobe, today=TODAY)
        assert [i["id"] for i in buckets["keep"]] == ["worn-yesterday"]
        assert buckets["donate"] == []

    def test_old_worn_item_goes_to_donate_bag(self, fresh_wardrobe: Wardrobe) -> None:
        add(fresh_wardrobe, name="dusty coat", last_worn="2026-01-15")  # 289 days
        buckets = triage(fresh_wardrobe, today=TODAY)
        assert [i["id"] for i in buckets["donate"]] == ["dusty-coat"]

    def test_never_worn_recent_is_your_call(self, fresh_wardrobe: Wardrobe) -> None:
        add(fresh_wardrobe, name="festival vest", added="2026-07-01")  # 122 days
        buckets = triage(fresh_wardrobe, today=TODAY)
        assert [i["id"] for i in buckets["your_call"]] == ["festival-vest"]

    def test_never_worn_very_old_is_donate(self, fresh_wardrobe: Wardrobe) -> None:
        add(fresh_wardrobe, name="ages-old tie", added="2025-01-15")
        buckets = triage(fresh_wardrobe, today=TODAY)
        assert [i["id"] for i in buckets["donate"]] == ["ages-old-tie"]

    def test_never_worn_new_gets_a_chance(self, fresh_wardrobe: Wardrobe) -> None:
        add(fresh_wardrobe, name="brand new hat", added="2026-10-01")
        buckets = triage(fresh_wardrobe, today=TODAY)
        assert [i["id"] for i in buckets["keep"]] == ["brand-new-hat"]

    def test_custom_threshold(self, fresh_wardrobe: Wardrobe) -> None:
        add(fresh_wardrobe, name="slow fade tee", last_worn="2026-08-20")  # 72 days
        assert triage(fresh_wardrobe, min_days=60, today=TODAY)["donate"]
        assert not triage(fresh_wardrobe, min_days=90, today=TODAY)["donate"]

    def test_donated_items_are_not_retriaged(self, sample_wardrobe: Wardrobe) -> None:
        buckets = triage(sample_wardrobe, today=TODAY)
        all_ids = [i["id"] for group in buckets.values() for i in group]
        assert "old-college-tee" not in all_ids


class TestTriageOnSample:
    def test_buckets_sort_descending_by_staleness(self, sample_wardrobe: Wardrobe) -> None:
        buckets = triage(sample_wardrobe, today=TODAY)
        ids = [i["id"] for i in buckets["donate"]]
        # green band shirt: Feb 14 (259d); black blazer: Mar 1 (244d);
        # red scarf: added Dec 20 2025 (315d, never worn)
        assert ids == ["red-scarf-gift", "green-band-shirt", "black-blazer"]

    def test_render_includes_donations_and_gentle_note(self, sample_wardrobe: Wardrobe) -> None:
        text = render_triage(triage(sample_wardrobe, today=TODAY), 180)
        assert "Donate bag" in text
        assert "never worn" in text
        assert "not a rule" in text
        assert "old college tee" not in text  # already donated, not re-triaged


class TestUnwornReport:
    def test_counts_unworn_and_favorite(self, sample_wardrobe: Wardrobe) -> None:
        report = unworn_report(sample_wardrobe, 90, TODAY)
        assert report["total"] == 8
        unworn_ids = {i["id"] for i in report["unworn"]}
        assert "green-band-shirt" in unworn_ids
        assert "navy-chinos" not in unworn_ids  # worn Oct 30
        assert report["most_worn"]["id"] == "decent-sneakers"

    def test_clean_closet_gets_compliment(self, fresh_wardrobe: Wardrobe) -> None:
        add(fresh_wardrobe, name="fresh tee", last_worn="2026-10-30")
        report = unworn_report(fresh_wardrobe, NEW_DAYS, TODAY)
        assert report["unworn"] == []
