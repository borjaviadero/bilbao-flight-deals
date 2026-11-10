"""One complete run of a flights instance: search, evaluate, record, alert.

Order of operations:

1. Fetch fares and select candidates.
2. Warm-up run (first ever, if enabled): no deals evaluated; one start message.
   Otherwise: evaluate candidates against the history *as it was before this run*,
   then plan alerts (no repeats, ranked, capped per run, rest in a summary). Super
   deals (see ``super_deals.py``) are taken out of the city topic and go to the
   group's General topic instead.
3. Record this run's prices.
4. Send the messages; each alert is logged right after it is delivered.
5. Mark the run as finished.

With ``dry_run`` nothing is written to the history and nothing is sent: the
messages are returned so they can be printed.
"""

from __future__ import annotations

import logging
import time
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
from flights_watcher.places import airline_names, city_coordinates, city_countries, city_names
from flights_watcher.price_api import TravelpayoutsClient
from flights_watcher.search import (
    fetch_fares,
    needs_coordinates,
    needs_countries,
    select_candidates,
)
from flights_watcher.super_deals import SuperDealCheck, check_super_deal

# Telegram allows about 20 messages per minute in one group: keep well under it.
SEND_INTERVAL_SECONDS = 3.0

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
    super_deals: int = 0
    messages: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)  # "topic" or "super", per message


def run_instance(
    config: FlightsInstanceConfig,
    client: TravelpayoutsClient,
    history: PriceHistory,
    send: Sender,
    *,
    send_super: Sender | None = None,
    now: datetime,
    http: JsonHttpClient | None = None,
    timezone: tzinfo,
    dry_run: bool = False,
    pause: Callable[[float], None] = time.sleep,
) -> RunReport:
    """Execute one run. ``now`` must be timezone-aware.

    ``send`` posts to the instance's topic; ``send_super`` to where super deals go
    (the group's General topic); without it super deals use ``send``.
    """
    instance = config.instance
    language = config.telegram.language
    today = now.astimezone(timezone).date()
    run_id = None if dry_run else history.start_run(instance, now)

    fares = fetch_fares(config, client, today)
    countries = (
        city_countries(http, history, now, store=not dry_run)
        if http is not None and needs_countries(config)
        else {}
    )
    coordinates = (
        city_coordinates(http, history, now, store=not dry_run)
        if http is not None and (needs_coordinates(config) or config.super_deals is not None)
        else {}
    )
    candidates = select_candidates(fares, config, today, countries, coordinates)
    warmup = config.alerts.warmup_first_run and history.completed_runs(instance) == 0
    report = RunReport(warmup=warmup, fetched=len(fares), candidates=len(candidates))

    downloaded = (
        city_names(http, history, language, now, store=not dry_run) if http is not None else {}
    )
    names = {**downloaded, **config.search.city_names}
    airlines = airline_names(http, history, now, store=not dry_run) if http is not None else {}

    plan: AlertPlan[Candidate] = AlertPlan(send=[], summary=[], skipped=[])
    supers: list[tuple[Opportunity[Candidate], SuperDealCheck]] = []
    if warmup:
        _add(report, "topic", start_message(config, candidates, len(candidates), language, names))
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
        if config.super_deals is not None:  # take super deals out of the city topic
            checks = {
                o.item_key: check_super_deal(o, config, history, now, coordinates)
                for o in [*plan.send, *plan.summary]
            }
            supers = [
                (o, checks[o.item_key])
                for o in [*plan.send, *plan.summary]
                if checks[o.item_key].is_super
            ]
            plan = AlertPlan(
                send=[o for o in plan.send if not checks[o.item_key].is_super],
                summary=[o for o in plan.summary if not checks[o.item_key].is_super],
                skipped=plan.skipped,
            )
        report.super_deals = len(supers)
        for o, check in supers:
            _add(report, "super", alert_message(o, config, language, names, airlines, check))
        for o in plan.send:
            _add(report, "topic", alert_message(o, config, language, names, airlines))
        if plan.summary:
            _add(
                report,
                "topic",
                summary_message(
                    plan.summary, language, names, max_alerts=config.alerts.max_per_run
                ),
            )

    if dry_run:
        report.alerts_sent = len(plan.send) + len(supers)
        report.in_summary = len(plan.summary)
        return report

    history.record(instance, to_observations(candidates, config.search.usual_price_by), now)

    delivered = 0

    def deliver(target: str, text: str) -> None:
        nonlocal delivered
        if delivered:
            pause(SEND_INTERVAL_SECONDS)
        sender = (send_super or send) if target == "super" else send
        sender(text)
        delivered += 1

    alerted = [o for o, _ in supers] + plan.send  # one message each, in this order
    messages = list(zip(report.targets, report.messages, strict=True))
    for opportunity, (target, text) in zip(alerted, messages[: len(alerted)], strict=True):
        deliver(target, text)
        _log_alert(history, instance, opportunity, now)
        report.alerts_sent += 1
    for target, text in messages[len(alerted) :]:  # summary or start message
        deliver(target, text)
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
        "run finished: %d fetched, %d candidates, %d deals, %d alerts (%d super deals), "
        "%d in summary, %d repeats skipped%s",
        report.fetched,
        report.candidates,
        report.deals,
        report.alerts_sent,
        report.super_deals,
        report.in_summary,
        report.skipped_repeats,
        " (warm-up)" if warmup else "",
    )
    return report


def _add(report: RunReport, target: str, text: str) -> None:
    report.targets.append(target)
    report.messages.append(text)


def _log_alert(
    history: PriceHistory, instance: str, opportunity: Opportunity[Candidate], now: datetime
) -> None:
    history.record_alert(instance, opportunity.item_key, opportunity.price, opportunity.window, now)
