"""Tests for super deals: itinerary check, price path and drop path."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from dealhunter_core.alerts import Opportunity
from dealhunter_core.history import Observation, PriceHistory
from dealhunter_core.rules import Evaluation
from flights_watcher.config import FlightsInstanceConfig, load_config
from flights_watcher.models import Candidate, Fare
from flights_watcher.super_deals import check_super_deal, direct_minutes, reasonable_itinerary

REPO_ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
COORDS = {
    "MAD": (40.42, -3.70),
    "NYC": (40.71, -74.01),
    "BIO": (43.30, -2.91),
    "ROM": (41.90, 12.50),
}
NYC = Fare(
    origin_airport="MAD",
    destination_airport="JFK",
    destination_city="NYC",
    departure_at=datetime(2027, 2, 6, 10, 0),
    return_at=datetime(2027, 2, 15, 18, 0),
    price_per_person=Decimal("300"),
    currency="EUR",
    airline="IB",
    flight_number="1",
    stops_out=0,
    stops_back=0,
    duration_minutes=1000,
    outbound_minutes=500,
    return_minutes=480,
    gate="g",
    link="https://example.test",
)


def cfg(code: str) -> FlightsInstanceConfig:
    return load_config(REPO_ROOT / "config" / "watchers" / f"flights-{code}.yaml")


def opp(fare: Fare) -> Opportunity[Candidate]:
    evaluation = Evaluation(is_deal=True, reasons=("test",), usual_price=None, drop_percent=None)
    return Opportunity(
        item_key=fare.key,
        price=fare.price_per_person,
        window="regular",
        evaluation=evaluation,
        item=Candidate(fare, "regular", 88),
    )


def seed(h: PriceHistory, instance: str, route: str, price: str, count: int) -> None:
    rows = [
        Observation(item_key=f"o{n}", route_key=route, price=Decimal(price), currency="EUR")
        for n in range(count)
    ]
    h.record(instance, rows, NOW - timedelta(days=2))


def test_direct_minutes_and_itinerary() -> None:
    direct = direct_minutes(NYC, "MAD", COORDS)
    assert direct is not None and 450 < direct < 470  # ~5,800 km at 800 km/h + 30 min
    c = cfg("mad")
    assert reasonable_itinerary(NYC, c, COORDS)  # direct
    via_bogota = replace(NYC, stops_out=1, outbound_minutes=1120)  # 18.7 h
    assert not reasonable_itinerary(via_bogota, c, COORDS)
    one_short_stop = replace(NYC, stops_out=1, outbound_minutes=700)  # 11.7 h < ~13.5 h
    assert reasonable_itinerary(one_short_stop, c, COORDS)
    assert not reasonable_itinerary(
        replace(one_short_stop, destination_city="XXX", destination_airport="XXX"), c, COORDS
    )


def test_long_haul_drop_path_needs_history_and_saving() -> None:
    c = cfg("mad")
    route = "MAD-JFK@2027-02"
    with PriceHistory.in_memory() as h:
        seed(h, "flights-mad", route, "700", 9)
        assert not check_super_deal(opp(NYC), c, h, NOW, COORDS).is_super  # only 9 prices
        seed(h, "flights-mad", route, "700", 1)
        check = check_super_deal(opp(NYC), c, h, NOW, COORDS)
        assert check.is_super and check.saving == Decimal("400")  # -57 %, 400 € saved
    with PriceHistory.in_memory() as h:
        seed(h, "flights-mad", route, "560", 10)
        assert not check_super_deal(opp(NYC), c, h, NOW, COORDS).is_super  # -46 %


def test_bilbao_price_path_and_minimum_saving() -> None:
    c = cfg("bio")
    rome = replace(
        NYC,
        origin_airport="BIO",
        destination_airport="FCO",
        destination_city="ROM",
        price_per_person=Decimal("19"),
        outbound_minutes=150,
        return_minutes=150,
    )
    with PriceHistory.in_memory() as h:
        assert check_super_deal(opp(rome), c, h, NOW, COORDS).is_super  # 19 € pp: no history
        seed(h, "flights-bio", "BIO-FCO", "60", 10)
        cheap = replace(rome, price_per_person=Decimal("25"))  # -58 % but only 35 € saved
        assert not check_super_deal(opp(cheap), c, h, NOW, COORDS).is_super
    with PriceHistory.in_memory() as h:
        seed(h, "flights-bio", "BIO-FCO", "120", 10)
        big = replace(rome, price_per_person=Decimal("55"))  # -54 %, 65 € saved
        assert check_super_deal(opp(big), c, h, NOW, COORDS).is_super
