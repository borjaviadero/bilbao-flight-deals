"""Tests for the search plan (months to query) and candidate selection."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from dealhunter_core.http import HttpResponse, JsonHttpClient
from flights_watcher.config import FlightsInstanceConfig, load_config
from flights_watcher.models import Fare
from flights_watcher.price_api import TravelpayoutsClient
from flights_watcher.search import departure_months, fetch_fares, select_candidates

REPO_ROOT = Path(__file__).resolve().parents[3]
TODAY = date(2026, 10, 27)


def config() -> FlightsInstanceConfig:
    return load_config(REPO_ROOT / "config" / "watchers" / "flights-bio.yaml")


def fare(days_ahead: int, price: str, *, stops: tuple[int, int] = (0, 0), **kw: str) -> Fare:
    out = datetime(2026, 10, 27, 10, 0) + timedelta(days=days_ahead)
    base = Fare(
        origin_airport="BIO",
        destination_airport="MXP",
        destination_city="MIL",
        departure_at=out,
        return_at=out + timedelta(days=4),
        price_per_person=Decimal(price),
        currency="EUR",
        airline="W4",
        flight_number="1",
        stops_out=stops[0],
        stops_back=stops[1],
        duration_minutes=240,
        outbound_minutes=120,
        gate="g",
        link="https://example.test",
    )
    return replace(base, **kw)  # type: ignore[arg-type]


def test_departure_months_crosses_year() -> None:
    assert departure_months(date(2026, 11, 3), date(2027, 2, 1)) == [
        "2026-11",
        "2026-12",
        "2027-01",
        "2027-02",
    ]
    assert departure_months(date(2026, 11, 3), date(2026, 11, 30)) == ["2026-11"]


def test_select_assigns_windows_and_drops_out_of_range() -> None:
    fares = [fare(3, "10"), fare(10, "20"), fare(45, "50"), fare(200, "5")]
    result = select_candidates(fares, config(), TODAY)
    assert [(c.window, c.days_ahead) for c in result] == [("last_minute", 10), ("regular", 45)]


def test_select_drops_too_many_stops_on_either_leg() -> None:
    fares = [fare(40, "30", stops=(0, 1)), fare(40, "20", stops=(2, 0), destination_airport="X")]
    result = select_candidates(fares, config(), TODAY)
    assert [c.fare.stops_back for c in result] == [1]


def test_select_deduplicates_keeping_cheapest_and_sorts() -> None:
    fares = [
        fare(40, "90"),
        fare(40, "70"),  # same trip, cheaper
        fare(50, "60", destination_airport="STN"),
        fare(60, "80", origin_airport="MAD"),  # other origin
    ]
    result = select_candidates(fares, config(), TODAY)
    assert [(c.fare.destination_airport, c.fare.price_per_person) for c in result] == [
        ("STN", Decimal("60")),
        ("MXP", Decimal("70")),
    ]


def test_fetch_fares_queries_every_month_of_the_windows() -> None:
    urls: list[str] = []
    body = json.dumps({"success": True, "data": []}).encode()

    def transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
        urls.append(request.full_url)
        return HttpResponse(200, body)

    client = TravelpayoutsClient("t", JsonHttpClient(transport=transport))
    assert fetch_fares(config(), client, TODAY) == []

    months = [
        dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query))["departure_at"] for u in urls
    ]
    # windows cover 7..180 days ahead: 2026-11-03 .. 2027-04-25
    assert months == ["2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04"]


def test_select_drops_trips_too_long_for_the_distance() -> None:
    short_trip = fare(40, "30")  # 4 nights, 2 h flight: allowed (2-7)
    too_long = replace(
        fare(40, "25", destination_airport="VLC"), return_at=datetime(2026, 12, 27, 10, 0)
    )  # 21 nights
    long_haul = replace(
        fare(40, "300", destination_airport="MEX"),
        return_at=datetime(2026, 12, 20, 10, 0),
        outbound_minutes=760,
    )  # 14 n
    result = select_candidates([short_trip, too_long, long_haul], config(), TODAY)
    assert sorted(c.fare.destination_airport for c in result) == ["MEX", "MXP"]
