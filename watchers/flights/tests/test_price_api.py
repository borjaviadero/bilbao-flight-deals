"""Tests for the Travelpayouts client and response parsing."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path

import pytest

from dealhunter_core.http import HttpResponse, JsonHttpClient
from flights_watcher.price_api import (
    PRICES_FOR_DATES,
    PriceApiError,
    TravelpayoutsClient,
    parse_prices_response,
)

FIXTURE = Path(__file__).parent / "fixtures" / "prices_for_dates.json"


def load_fixture() -> dict[str, object]:
    data: dict[str, object] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data


def test_parse_valid_fares_and_skip_malformed() -> None:
    fares = parse_prices_response(load_fixture(), currency="EUR")
    assert [f.destination_airport for f in fares] == ["MXP", "STN", "BKK"]  # MAD lacks fields

    milan = fares[0]
    assert milan.price_per_person == Decimal("26")
    assert milan.currency == "EUR"
    assert milan.airline == "W4"
    assert (milan.stops_out, milan.stops_back) == (0, 0)
    assert milan.nights == 7
    assert milan.link.startswith("https://www.aviasales.com/search/")
    assert milan.total_price(2) == Decimal("52")


def test_parse_error_payload() -> None:
    with pytest.raises(PriceApiError, match="Unauthorized"):
        parse_prices_response({"success": False, "error": "Unauthorized"}, currency="EUR")
    with pytest.raises(PriceApiError):
        parse_prices_response({"success": True}, currency="EUR")
    with pytest.raises(PriceApiError):
        parse_prices_response(["not", "a", "mapping"], currency="EUR")


def test_client_request() -> None:
    requests: list[urllib.request.Request] = []

    def transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
        requests.append(request)
        return HttpResponse(200, FIXTURE.read_bytes())

    client = TravelpayoutsClient("tok-123", JsonHttpClient(transport=transport))
    fares = client.round_trip_fares(
        origin="BIO", currency="EUR", departure_month="2026-12", destination="LON"
    )

    assert len(fares) == 3
    request = requests[0]
    url = urllib.parse.urlsplit(request.full_url)
    params = dict(urllib.parse.parse_qsl(url.query))
    assert f"{url.scheme}://{url.netloc}{url.path}" == PRICES_FOR_DATES
    assert params == {
        "origin": "BIO",
        "currency": "eur",
        "market": "es",
        "one_way": "false",
        "sorting": "price",
        "limit": "1000",
        "departure_at": "2026-12",
        "destination": "LON",
    }
    assert request.get_header("X-access-token") == "tok-123"
    assert "tok-123" not in request.full_url
