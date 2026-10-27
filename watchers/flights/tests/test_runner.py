"""Tests for a complete run: warm-up, alerts, repeats, cap, dry run and failures."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from dealhunter_core.history import PriceHistory
from dealhunter_core.http import HttpResponse, JsonHttpClient
from flights_watcher.config import FlightsInstanceConfig, load_config
from flights_watcher.price_api import TravelpayoutsClient
from flights_watcher.runner import SEND_INTERVAL_SECONDS, run_instance

REPO_ROOT = Path(__file__).resolve().parents[3]
MADRID = ZoneInfo("Europe/Madrid")
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def fare(dest: str, price: int, out: str, back: str) -> dict[str, Any]:
    return {
        "origin": "BIO",
        "destination": dest,
        "origin_airport": "BIO",
        "destination_airport": dest,
        "price": price,
        "airline": "VY",
        "flight_number": "1",
        "departure_at": f"{out}T08:00:00+01:00",
        "return_at": f"{back}T20:00:00+01:00",
        "transfers": 0,
        "return_transfers": 0,
        "duration": 200,
        "gate": "g",
        "link": f"/search/{dest}",
    }


# 16 days ahead → last_minute (deal if ≤ 30); 44 days ahead → regular (deal if ≤ 40)
DEFAULT_FARES = [
    fare("MXP", 26, "2026-11-12", "2026-11-19"),  # last minute deal
    fare("STN", 41, "2026-12-10", "2026-12-14"),  # regular, not a deal
    fare("VLC", 35, "2026-12-10", "2026-12-14"),  # regular deal
]


def client(fares: list[dict[str, Any]]) -> TravelpayoutsClient:
    body = json.dumps({"success": True, "data": fares}).encode()

    def transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
        return HttpResponse(200, body)

    return TravelpayoutsClient("t", JsonHttpClient(transport=transport))


def config(**alerts: Any) -> FlightsInstanceConfig:
    cfg = load_config(REPO_ROOT / "config" / "watchers" / "flights-bio.yaml")
    if alerts:
        cfg = cfg.model_copy(update={"alerts": cfg.alerts.model_copy(update=alerts)})
    return cfg


def run(
    history: PriceHistory,
    sent: list[str],
    *,
    now: datetime = NOW,
    fares: list[dict[str, Any]] = DEFAULT_FARES,
    cfg: FlightsInstanceConfig | None = None,
    dry_run: bool = False,
) -> Any:
    return run_instance(
        cfg or config(),
        client(fares),
        history,
        sent.append,
        now=now,
        timezone=MADRID,
        dry_run=dry_run,
        pause=lambda _: None,
    )


def test_first_run_is_a_warm_up() -> None:
    sent: list[str] = []
    with PriceHistory.in_memory() as h:
        report = run(h, sent)
        assert report.warmup
        assert (report.candidates, report.alerts_sent) == (3, 0)
        assert len(sent) == 1 and "Empiezo a vigilar" in sent[0]
        assert h.completed_runs("flights-bio") == 1
        assert h.last_alert_price("flights-bio", "BIO|MXP|2026-11-12|2026-11-19|VY") is None


def test_second_run_alerts_and_third_does_not_repeat() -> None:
    sent: list[str] = []
    with PriceHistory.in_memory() as h:
        run(h, sent)
        sent.clear()

        second = run(h, sent, now=NOW + timedelta(hours=6))
        assert not second.warmup
        assert (second.deals, second.alerts_sent, second.in_summary) == (2, 2, 0)
        assert "MXP" in sent[0] and "VLC" in sent[1]  # no history yet: cheapest first
        sent.clear()

        third = run(h, sent, now=NOW + timedelta(hours=12))
        assert (third.deals, third.alerts_sent, third.skipped_repeats) == (2, 0, 2)
        assert sent == []


def test_cap_puts_the_rest_in_a_summary() -> None:
    sent: list[str] = []
    with PriceHistory.in_memory() as h:
        run(h, sent)
        sent.clear()
        report = run(h, sent, now=NOW + timedelta(hours=6), cfg=config(max_per_run=1))
        assert (report.alerts_sent, report.in_summary) == (1, 1)
        assert len(sent) == 2 and "no cabía en los 1 avisos" in sent[1]
        # the summarised deal is not announced again
        sent.clear()
        report = run(h, sent, now=NOW + timedelta(hours=12), cfg=config(max_per_run=1))
        assert report.alerts_sent == 0


def test_dry_run_writes_and_sends_nothing() -> None:
    sent: list[str] = []
    with PriceHistory.in_memory() as h:
        report = run(h, sent, dry_run=True)
        assert report.warmup and len(report.messages) == 1
        assert sent == []
        assert h.completed_runs("flights-bio") == 0


def test_warm_up_can_be_disabled() -> None:
    sent: list[str] = []
    with PriceHistory.in_memory() as h:
        report = run(h, sent, cfg=config(warmup_first_run=False))
        assert not report.warmup
        assert report.alerts_sent == 2


def test_failed_send_leaves_the_run_unfinished() -> None:
    def failing(text: str) -> None:
        raise RuntimeError("Telegram is down")

    with PriceHistory.in_memory() as h:
        with pytest.raises(RuntimeError):
            run_instance(config(), client(DEFAULT_FARES), h, failing, now=NOW, timezone=MADRID)
        assert h.completed_runs("flights-bio") == 0  # next run is still a warm-up


def test_messages_are_spaced_out() -> None:
    sent: list[str] = []
    pauses: list[float] = []
    with PriceHistory.in_memory() as h:
        run(h, sent)
        sent.clear()
        run_instance(
            config(),
            client(DEFAULT_FARES),
            h,
            sent.append,
            now=NOW + timedelta(hours=6),
            timezone=MADRID,
            pause=pauses.append,
        )
    assert len(sent) == 2
    assert pauses == [SEND_INTERVAL_SECONDS]  # between messages, not before the first
