"""Tests for the flights side of history and rules."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter_core.history import Observation, PriceHistory
from flights_watcher.config import FlightsInstanceConfig, load_config
from flights_watcher.deals import find_opportunities, route_key, to_observations
from flights_watcher.models import Candidate, Fare

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
BASE = Fare(
    origin_airport="BIO",
    destination_airport="MXP",
    destination_city="MIL",
    departure_at=datetime(2026, 12, 10, 8, 0),
    return_at=datetime(2026, 12, 14, 20, 0),
    price_per_person=Decimal("50"),
    currency="EUR",
    airline="VY",
    flight_number="1",
    stops_out=0,
    stops_back=0,
    duration_minutes=240,
    outbound_minutes=120,
    gate="g",
    link="https://example.test",
)


def config() -> FlightsInstanceConfig:
    return load_config(REPO_ROOT / "config" / "watchers" / "flights-bio.yaml")


def candidate(price: str, window: str = "regular", **kw: object) -> Candidate:
    fare = replace(BASE, price_per_person=Decimal(price), **kw)  # type: ignore[arg-type]
    return Candidate(fare=fare, window=window, days_ahead=44 if window == "regular" else 10)


def seed(history: PriceHistory, price: str, count: int = 5) -> None:
    rows = [
        Observation(item_key=f"old-{n}", route_key="BIO-MXP", price=Decimal(price), currency="EUR")
        for n in range(count)
    ]
    history.record("flights-bio", rows, NOW - timedelta(days=3))


def test_route_key_and_observations() -> None:
    c = candidate("50")
    assert route_key(c.fare) == "BIO-MXP"
    [row] = to_observations([c])
    assert (row.item_key, row.route_key, row.price) == (c.fare.key, "BIO-MXP", Decimal("50"))


def test_without_history_only_the_price_cap_applies() -> None:
    cfg = config()
    with PriceHistory.in_memory() as history:
        found = find_opportunities(
            [
                candidate("40"),
                candidate("41", airline="FR"),
                candidate("30", "last_minute"),
                candidate("31", "last_minute", airline="U2"),
            ],
            cfg,
            history,
            NOW,
        )
    assert [(o.window, o.price) for o in found] == [
        ("regular", Decimal("40")),
        ("last_minute", Decimal("30")),
    ]
    assert all(o.evaluation.usual_price is None for o in found)


def test_with_history_the_drop_rule_applies() -> None:
    cfg = config()
    with PriceHistory.in_memory() as history:
        seed(history, "100")
        found = find_opportunities(
            [
                candidate("65"),
                candidate("75", airline="FR"),
                candidate("60", "last_minute"),
                candidate("50", "last_minute", airline="U2"),
            ],
            cfg,
            history,
            NOW,
        )
    # regular needs -30% (65 ok, 75 not); last minute needs -50% (50 ok, 60 not)
    assert [(o.window, o.price, o.evaluation.drop_percent) for o in found] == [
        ("regular", Decimal("65"), Decimal("35.0")),
        ("last_minute", Decimal("50"), Decimal("50.0")),
    ]


def test_old_history_is_ignored() -> None:
    cfg = config()
    with PriceHistory.in_memory() as history:
        history.record(
            "flights-bio",
            [Observation(f"o{n}", "BIO-MXP", Decimal("100"), "EUR") for n in range(5)],
            NOW - timedelta(days=31),
        )
        assert find_opportunities([candidate("65")], cfg, history, NOW) == []


def test_unknown_window_name() -> None:
    with pytest.raises(KeyError):
        config().window_named("nope")
