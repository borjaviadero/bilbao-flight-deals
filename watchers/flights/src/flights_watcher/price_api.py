"""Client for the Travelpayouts / Aviasales Data API.

Only the endpoint the watcher needs is implemented:
``GET /aviasales/v3/prices_for_dates`` (cached round-trip prices).
See ``docs/price-source.md`` for what the data is and is not.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from dealhunter_core.http import JsonHttpClient
from flights_watcher.models import Fare

logger = logging.getLogger(__name__)

BASE_URL = "https://api.travelpayouts.com"
PRICES_FOR_DATES = f"{BASE_URL}/aviasales/v3/prices_for_dates"
BOOKING_BASE_URL = "https://www.aviasales.com"
MAX_LIMIT = 1000


class PriceApiError(Exception):
    """The price API answered with an error or an unexpected payload."""


class TravelpayoutsClient:
    """Fetches round-trip fares. The token travels in a header, never in the URL."""

    def __init__(self, token: str, http: JsonHttpClient, *, market: str = "es") -> None:
        self._headers = {"X-Access-Token": token}
        self._http = http
        self._market = market

    def round_trip_fares(
        self,
        *,
        origin: str,
        currency: str,
        departure_month: str | None = None,
        destination: str | None = None,
        limit: int = MAX_LIMIT,
    ) -> list[Fare]:
        """Cheapest cached round-trip fares from ``origin``.

        ``departure_month`` is ``YYYY-MM``; without ``destination`` the API returns
        fares to any destination.
        """
        params: dict[str, str | int] = {
            "origin": origin,
            "currency": currency.lower(),
            "market": self._market,
            "one_way": "false",
            "sorting": "price",
            "limit": min(limit, MAX_LIMIT),
        }
        if departure_month:
            params["departure_at"] = departure_month
        if destination:
            params["destination"] = destination

        payload = self._http.get_json(PRICES_FOR_DATES, params=params, headers=self._headers)
        return parse_prices_response(payload, currency=currency.upper())


def parse_prices_response(payload: Any, *, currency: str) -> list[Fare]:
    """Turn a ``prices_for_dates`` response into fares, skipping malformed entries."""
    if not isinstance(payload, Mapping) or payload.get("success") is not True:
        error = payload.get("error") if isinstance(payload, Mapping) else None
        raise PriceApiError(f"price API returned an error: {error or payload!r}")

    data = payload.get("data")
    if not isinstance(data, list):
        raise PriceApiError("price API response has no 'data' list")

    fares: list[Fare] = []
    for item in data:
        try:
            fares.append(_parse_fare(item, currency))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            logger.warning("skipping malformed fare %r: %s", item, exc)
    return fares


def _parse_fare(item: Mapping[str, Any], currency: str) -> Fare:
    if not item.get("return_at"):
        raise ValueError("not a round trip")
    link = str(item.get("link", ""))
    total = int(item.get("duration") or 0)  # both legs, layovers included
    outbound = int(item.get("duration_to") or total // 2)
    return Fare(
        origin_airport=str(item["origin_airport"]),
        destination_airport=str(item["destination_airport"]),
        destination_city=str(item["destination"]),
        departure_at=datetime.fromisoformat(item["departure_at"]),
        return_at=datetime.fromisoformat(item["return_at"]),
        price_per_person=Decimal(str(item["price"])),
        currency=currency,
        airline=str(item.get("airline", "")),
        flight_number=str(item.get("flight_number", "")),
        stops_out=int(item.get("transfers", 0)),
        stops_back=int(item.get("return_transfers", 0)),
        duration_minutes=int(item.get("duration", 0)),
        outbound_minutes=outbound,
        return_minutes=int(item.get("duration_back") or (total - outbound if total else 0)),
        gate=str(item.get("gate", "")),
        link=f"{BOOKING_BASE_URL}{link}" if link.startswith("/") else link,
    )
