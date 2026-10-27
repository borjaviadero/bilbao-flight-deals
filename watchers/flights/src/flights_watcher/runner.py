"""One complete run of a flights instance: search, evaluate, record, alert.

Order of operations:

1. Fetch fares and select candidates.
2. Warm-up run (first ever, if enabled): no deals evaluated; one start message.
   Otherwise: evaluate candidates against the history *as it was before this run*,
   then plan alerts (no repeats, ranked, capped per run, rest in a summary).
3. Record this run's prices.
4. Send the messages; each alert is logged right after it is delivered.
5. Mark the run as finished.

With ``dry_run`` nothing is written to the history and nothing is sent: the
messages are returned so they can be printed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, tzinfo

from dealhunter_core.alerts import AlertPlan, Opportunity, plan_alerts
from dealhunter_core.history import PriceHistory
from dealhunter_core.http import JsonHttpClient
from flights_watcher.config import FlightsInstanceConfig
from flights_watcher.deals import find_opportunities, to_observations
from flights_watcher.messages import alert_message, start_message, summary_message
from flights_watcher.models import Candidate
from flights_watcher.places import city_names
from flights_watcher.price_api import TravelpayoutsClient
from flights_watcher.search import fetch_fares, select_candidates

logger = logging.getLogger(__name__)

Sender = Callable[[str], None]


@dataclass(slots=True)
class RunReport:
    """What happened in a run."""

    warmup: bool
    fetched: int
    candidates: int
    deals: int = 0
    alerts_sent: int = 0
    in_summary: int = 0
    skipped_repeats: int = 0
    messages: list[str] = field(default_factory=list)


def run_instance(
    config: FlightsInstanceConfig,
    client: TravelpayoutsClient,
    history: PriceHistory,
    send: Sender,
    *,
    now: datetime,
    http: JsonHttpClient | None = None,
    timezone: tzinfo,
    dry_run: bool = False,
) -> RunReport:
    """Execute one run. ``now`` must be timezone-aware."""
    instance = config.instance
    language = config.telegram.language
    today = now.astimezone(timezone).date()
    run_id = None if dry_run else history.start_run(instance, now)

    fares = fetch_fares(config, client, today)
    candidates = select_candidates(fares, config, today)
    warmup = config.alerts.warmup_first_run and history.completed_runs(instance) == 0
    report = RunReport(warmup=warmup, fetched=len(fares), candidates=len(candidates))

    names = city_names(http, history, language, now, store=not dry_run) if http is not None else {}

    plan: AlertPlan[Candidate] = AlertPlan(send=[], summary=[], skipped=[])
    if warmup:
        report.messages.append(start_message(config, candidates, len(candidates), language, names))
    else:
        opportunities = find_opportunities(candidates, config, history, now)
        plan = plan_alerts(
            opportunities,
            last_alert_price=lambda key: history.last_alert_price(instance, key),
            repeat_only_if_lower=config.alerts.repeat_only_if_lower,
            max_per_run=config.alerts.max_per_run,
        )
        report.deals = len(opportunities)
        report.skipped_repeats = len(plan.skipped)
        report.messages += [alert_message(o, config, language, names) for o in plan.send]
        if plan.summary:
            report.messages.append(summary_message(plan.summary, language, names))

    if dry_run:
        report.alerts_sent = len(plan.send)
        report.in_summary = len(plan.summary)
        return report

    history.record(instance, to_observations(candidates), now)

    alert_messages = report.messages[: len(plan.send)]
    for opportunity, text in zip(plan.send, alert_messages, strict=True):
        send(text)
        _log_alert(history, instance, opportunity, now)
        report.alerts_sent += 1
    for text in report.messages[len(plan.send) :]:  # summary or start message
        send(text)
    for opportunity in plan.summary:  # announced in the summary: do not repeat them
        _log_alert(history, instance, opportunity, now)
    report.in_summary = len(plan.summary)

    assert run_id is not None
    history.finish_run(
        run_id,
        now,
        fetched=report.fetched,
        candidates=report.candidates,
        alerts_sent=report.alerts_sent,
        warmup=warmup,
    )
    logger.info(
        "run finished: %d fetched, %d candidates, %d deals, %d alerts, %d in summary, "
        "%d repeats skipped%s",
        report.fetched,
        report.candidates,
        report.deals,
        report.alerts_sent,
        report.in_summary,
        report.skipped_repeats,
        " (warm-up)" if warmup else "",
    )
    return report


def _log_alert(
    history: PriceHistory, instance: str, opportunity: Opportunity[Candidate], now: datetime
) -> None:
    history.record_alert(instance, opportunity.item_key, opportunity.price, opportunity.window, now)
