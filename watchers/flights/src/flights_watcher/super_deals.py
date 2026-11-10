"""Super deals: the best opportunities of a run, posted to the group's General topic.

An opportunity (already a deal by its window's rules) becomes a super deal when it meets
the instance's ``super_deals`` rule (see ``SuperDealRule``): rare, a large saving in
euros, a usual price backed by enough history, and a reasonable itinerary.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from dealhunter_core.alerts import Opportunity
from dealhunter_core.history import PriceHistory
from flights_watcher.config import FlightsInstanceConfig
from flights_watcher.deals import route_key
from flights_watcher.models import Candidate, Fare
from flights_watcher.places import distance_km

CRUISE_KMH = 800  # average speed of a direct flight, gate to gate
TAXI_MINUTES = 30  # take-off, landing and taxiing

Coordinates = Mapping[str, tuple[float, float]]


@dataclass(frozen=True, slots=True)
class SuperDealCheck:
    """Verdict for one opportunity; ``saving`` is per person, when the usual price is known."""

    is_super: bool
    saving: Decimal | None = None
    usual: Decimal | None = None


def direct_minutes(fare: Fare, origin: str, coordinates: Coordinates) -> float | None:
    """Estimated flight time of a direct flight on the route, or None if unknown."""
    a = coordinates.get(fare.origin_airport) or coordinates.get(origin)
    b = coordinates.get(fare.destination_city) or coordinates.get(fare.destination_airport)
    if a is None or b is None:
        return None
    return distance_km(a, b) / CRUISE_KMH * 60 + TAXI_MINUTES


def reasonable_itinerary(
    fare: Fare, config: FlightsInstanceConfig, coordinates: Coordinates
) -> bool:
    """Each leg with a stop lasts at most ``max_detour_factor`` times the direct time."""
    rule = config.super_deals
    if rule is None:
        return False
    if fare.max_stops == 0:
        return True
    direct = direct_minutes(fare, config.search.origin, coordinates)
    if direct is None:
        return False  # cannot check: not a super deal
    limit = direct * rule.max_detour_factor
    for stops, minutes in (
        (fare.stops_out, fare.outbound_minutes),
        (fare.stops_back, fare.return_minutes),
    ):
        if stops > 0 and (minutes <= 0 or minutes > limit):
            return False
    return True


def check_super_deal(
    opportunity: Opportunity[Candidate],
    config: FlightsInstanceConfig,
    history: PriceHistory,
    now: datetime,
    coordinates: Coordinates,
) -> SuperDealCheck:
    """Whether a deal is a super deal. Call before recording the run's prices."""
    rule = config.super_deals
    fare = opportunity.item.fare
    if rule is None or not reasonable_itinerary(fare, config, coordinates):
        return SuperDealCheck(False)

    window = config.window_named(opportunity.window)
    lookback = window.drop_rule.lookback_days if window.drop_rule else 30
    usual = history.usual_price(
        config.instance,
        route_key(fare, config.search.usual_price_by),
        since=now - timedelta(days=lookback),
        min_observations=rule.min_observations,
    )
    price = fare.price_per_person
    saving = usual - price if usual is not None else None

    if rule.max_price_per_person is not None and price <= rule.max_price_per_person:
        return SuperDealCheck(True, saving, usual)
    if rule.min_drop_percent is not None and usual is not None and usual > 0 and saving:
        drop = saving / usual * 100
        if drop >= rule.min_drop_percent and saving >= rule.min_saving_per_person:
            return SuperDealCheck(True, saving, usual)
    return SuperDealCheck(False, saving, usual)
