"""Tests for the SQLite price history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter_core.history import Observation, PriceHistory

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def obs(price: str, route: str = "BIO-MXP", item: str = "trip-1") -> Observation:
    return Observation(item_key=item, route_key=route, price=Decimal(price), currency="EUR")


def test_usual_price_is_the_median() -> None:
    with PriceHistory.in_memory() as h:
        h.record("i", [obs("50"), obs("60"), obs("70"), obs("200"), obs("10")], NOW)
        assert h.usual_price(
            "i", "BIO-MXP", since=NOW - timedelta(days=30), min_observations=5
        ) == Decimal("60")  # 10, 50, [60], 70, 200 — the outlier 200 does not matter


def test_usual_price_needs_enough_observations() -> None:
    with PriceHistory.in_memory() as h:
        h.record("i", [obs("50"), obs("60")], NOW)
        assert (
            h.usual_price("i", "BIO-MXP", since=NOW - timedelta(days=1), min_observations=3) is None
        )


def test_usual_price_ignores_old_other_routes_and_instances() -> None:
    with PriceHistory.in_memory() as h:
        h.record("i", [obs("999")], NOW - timedelta(days=40))
        h.record("i", [obs("888", route="BIO-STN")], NOW)
        h.record("other", [obs("777")], NOW)
        h.record("i", [obs("40"), obs("60")], NOW)
        assert h.usual_price(
            "i", "BIO-MXP", since=NOW - timedelta(days=30), min_observations=2
        ) == Decimal("50")


def test_runs_count_only_finished() -> None:
    with PriceHistory.in_memory() as h:
        assert h.completed_runs("i") == 0
        first = h.start_run("i", NOW)
        assert h.completed_runs("i") == 0
        h.finish_run(first, NOW, fetched=10, candidates=5, alerts_sent=0, warmup=True)
        h.start_run("i", NOW)  # unfinished (e.g. crashed)
        assert h.completed_runs("i") == 1
        assert h.completed_runs("other") == 0


def test_alert_log_upserts() -> None:
    with PriceHistory.in_memory() as h:
        assert h.last_alert_price("i", "trip-1") is None
        h.record_alert("i", "trip-1", Decimal("40"), "regular", NOW)
        h.record_alert("i", "trip-1", Decimal("35"), "regular", NOW + timedelta(hours=6))
        assert h.last_alert_price("i", "trip-1") == Decimal("35")


def test_rejects_naive_datetimes() -> None:
    with PriceHistory.in_memory() as h, pytest.raises(ValueError, match="timezone"):
        h.start_run("i", datetime(2026, 1, 1))


def test_file_database_persists(tmp_path: Path) -> None:
    path = tmp_path / "data" / "history.sqlite3"
    with PriceHistory(path) as h:
        h.record("i", [obs("10")], NOW)
    with PriceHistory(path) as h:
        assert h.usual_price("i", "BIO-MXP", since=NOW, min_observations=1) == Decimal("10")


def test_cache_round_trip_and_expiry() -> None:
    with PriceHistory.in_memory() as h:
        assert h.cached("cities:es", max_age=timedelta(days=30), now=NOW) is None
        h.store_cache("cities:es", {"MIL": "Milán"}, NOW)
        assert h.cached("cities:es", max_age=timedelta(days=30), now=NOW) == {"MIL": "Milán"}
        later = NOW + timedelta(days=31)
        assert h.cached("cities:es", max_age=timedelta(days=30), now=later) is None
        h.store_cache("cities:es", {"MIL": "Milano"}, later)
        assert h.cached("cities:es", max_age=timedelta(days=30), now=later) == {"MIL": "Milano"}
