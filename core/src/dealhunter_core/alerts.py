"""Which deals become alerts in a run.

Given the deals found in a run, decide which are sent as individual alerts and which
only appear in a summary: skip items already alerted at the same or a lower price,
rank the rest, and cap the individual alerts per run.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from dealhunter_core.rules import Evaluation


@dataclass(frozen=True, slots=True)
class Opportunity[T]:
    """A deal found in a run. ``item`` is the watcher's own object (e.g. a flight)."""

    item_key: str
    price: Decimal
    window: str
    evaluation: Evaluation
    item: T


@dataclass(frozen=True, slots=True)
class AlertPlan[T]:
    """What to do with the deals of a run."""

    send: list[Opportunity[T]]
    summary: list[Opportunity[T]]
    skipped: list[Opportunity[T]]


def rank_key(opportunity: Opportunity[object]) -> tuple[Decimal, Decimal]:
    """Best first: biggest drop vs usual (unknown counts as 0), then lowest price."""
    drop = opportunity.evaluation.drop_percent or Decimal(0)
    return (-drop, opportunity.price)


def plan_alerts[T](
    opportunities: Sequence[Opportunity[T]],
    *,
    last_alert_price: Callable[[str], Decimal | None],
    repeat_only_if_lower: bool,
    max_per_run: int,
) -> AlertPlan[T]:
    """Split a run's deals into alerts to send, summary lines and skipped repeats."""
    fresh: list[Opportunity[T]] = []
    skipped: list[Opportunity[T]] = []
    for opportunity in opportunities:
        previous = last_alert_price(opportunity.item_key)
        if previous is not None and (not repeat_only_if_lower or opportunity.price >= previous):
            skipped.append(opportunity)
        else:
            fresh.append(opportunity)

    ranked = sorted(fresh, key=rank_key)
    return AlertPlan(send=ranked[:max_per_run], summary=ranked[max_per_run:], skipped=skipped)
