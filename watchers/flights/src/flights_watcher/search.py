"""Search: which requests to make for an instance, and which fares to keep."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import date, timedelta

from flights_watcher.config import FlightsInstanceConfig
from flights_watcher.models import Candidate, Fare
from flights_watcher.price_api import TravelpayoutsClient

logger = logging.getLogger(__name__)


def departure_months(first: date, last: date) -> list[str]:
    """Every ``YYYY-MM`` month between two dates, both included."""
    months: list[str] = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def fetch_fares(
    config: FlightsInstanceConfig, client: TravelpayoutsClient, today: date
) -> list[Fare]:
    """Query the price API for every month covered by the instance's deal windows."""
    first = today + timedelta(days=config.min_days_ahead)
    last = today + timedelta(days=config.max_days_ahead)
    destinations: list[str | None] = (
        [None] if config.search.destinations == "any" else list(config.search.destinations)
    )

    fares: list[Fare] = []
    for month in departure_months(first, last):
        for destination in destinations:
            batch = client.round_trip_fares(
                origin=config.search.origin,
                currency=config.search.currency,
                departure_month=month,
                destination=destination,
            )
            logger.info(
                "%s %s → %s: %d fares",
                month,
                config.search.origin,
                destination or "any",
                len(batch),
            )
            fares.extend(batch)
    return fares


def select_candidates(
    fares: Iterable[Fare],
    config: FlightsInstanceConfig,
    today: date,
    countries: Mapping[str, str] | None = None,
) -> list[Candidate]:
    """Keep fares that fit the search and fall into a deal window.

    Drops fares with too many stops, stops on a trip to a ``direct_only_countries``
    destination (``countries`` maps city codes to countries; unknown cities are kept),
    a trip length that does not fit the flight time, or a departure outside every
    window; removes duplicates
    (same route, dates and carrier) keeping the cheapest, and sorts by price.
    """
    best: dict[str, Candidate] = {}
    for fare in fares:
        if fare.origin_airport != config.search.origin:
            continue
        if fare.max_stops > config.search.max_stops:
            continue
        if fare.max_stops > 0 and _direct_only(fare, config, countries or {}):
            continue
        if not config.search.nights_allowed(fare.outbound_minutes, fare.nights):
            continue
        days = fare.days_ahead(today)
        window = config.window_for(days)
        if window is None:
            continue
        current = best.get(fare.key)
        if current is None or fare.price_per_person < current.fare.price_per_person:
            best[fare.key] = Candidate(fare=fare, window=window.name, days_ahead=days)

    return sorted(best.values(), key=lambda c: (c.fare.price_per_person, c.days_ahead))


def _direct_only(fare: Fare, config: FlightsInstanceConfig, countries: Mapping[str, str]) -> bool:
    """Whether the destination's country only accepts direct flights."""
    country = countries.get(fare.destination_city) or countries.get(fare.destination_airport)
    return country is not None and country in config.search.direct_only_countries
