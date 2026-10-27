"""Tests for city names (download, cache, fallbacks)."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta

from dealhunter_core.history import PriceHistory
from dealhunter_core.http import HttpResponse, JsonHttpClient
from flights_watcher.places import city_names, parse_cities

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
CITIES = [{"code": "MIL", "name": "Milán"}, {"code": "VLC", "name": "Valencia"}, {"code": "X"}]


def http(responses: list[HttpResponse], calls: list[str]) -> JsonHttpClient:
    def transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
        calls.append(request.full_url)
        return responses.pop(0)

    return JsonHttpClient(transport=transport, retries=0, sleep=lambda _: None)


def test_parse_cities() -> None:
    assert parse_cities(CITIES) == {"MIL": "Milán", "VLC": "Valencia"}
    assert parse_cities({"not": "a list"}) == {}


def test_downloads_once_then_uses_the_cache() -> None:
    calls: list[str] = []
    client = http([HttpResponse(200, json.dumps(CITIES).encode())], calls)
    with PriceHistory.in_memory() as h:
        assert city_names(client, h, "es", NOW)["MIL"] == "Milán"
        assert city_names(client, h, "es", NOW + timedelta(days=1))["VLC"] == "Valencia"
    assert calls == ["https://api.travelpayouts.com/data/es/cities.json"]


def test_failure_falls_back_to_codes() -> None:
    calls: list[str] = []
    client = http([HttpResponse(503, b"")], calls)
    with PriceHistory.in_memory() as h:
        assert city_names(client, h, "es", NOW) == {}


def test_dry_run_does_not_store() -> None:
    calls: list[str] = []
    client = http([HttpResponse(200, json.dumps(CITIES).encode())] * 2, calls)
    with PriceHistory.in_memory() as h:
        city_names(client, h, "es", NOW, store=False)
        assert h.cached("cities:es", max_age=timedelta(days=30), now=NOW) is None
