"""Flights side of history and deal rules: keys, observations and opportunities."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from dealhunter_core.alerts import Opportunity
from dealhunter_core.history import Observation, PriceHistory
from dealhunter_core.rules import evaluate
from flights_watcher.config import FlightsInstanceConfig
from flights_watcher.models import Candidate, Fare


def route_key(fare: Fare) -> str:
    """Route used for the usual price: origin and destination airports (any dates)."""
    return f"{fare.origin_airport}-{fare.destination_airport}"


def to_observations(candidates: Iterable[Candidate]) -> list[Observation]:
    """Turn a run's candidates into history rows."""
    return [
        Observation(
            item_key=c.fare.key,
            route_key=route_key(c.fare),
            price=c.fare.price_per_person,
            currency=c.fare.currency,
        )
        for c in candidates
    ]


def find_opportunities(
    candidates: Iterable[Candidate],
    config: FlightsInstanceConfig,
    history: PriceHistory,
    now: datetime,
) -> list[Opportunity[Candidate]]:
    """Evaluate every candidate against its window's rules; keep the deals.

    Call this **before** recording the run's observations, so a price is compared
    with the history that existed before it was seen.
    """
    opportunities: list[Opportunity[Candidate]] = []
    for candidate in candidates:
        window = config.window_named(candidate.window)
        usual = None
        if (rule := window.drop_rule) is not None:
            usual = history.usual_price(
                config.instance,
                route_key(candidate.fare),
                since=now - timedelta(days=rule.lookback_days),
                min_observations=rule.min_observations,
            )
        evaluation = evaluate(window, candidate.fare.price_per_person, usual)
        if evaluation.is_deal:
            opportunities.append(
                Opportunity(
                    item_key=candidate.fare.key,
                    price=candidate.fare.price_per_person,
                    window=candidate.window,
                    evaluation=evaluation,
                    item=candidate,
                )
            )
    return opportunities
