"""Tests for the command-line interface."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dealhunter_core.http import HttpResponse
from flights_watcher.cli import format_candidates, main

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = str(REPO_ROOT / "config" / "watchers" / "flights-bio.yaml")
FIXTURE = Path(__file__).parent / "fixtures" / "prices_for_dates.json"


def fixture_transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
    return HttpResponse(200, FIXTURE.read_bytes())


def test_search_without_token_fails_cleanly() -> None:
    code = main(["search", "--config", CONFIG], environ={}, transport=fixture_transport)
    assert code == 1


def test_search_with_bad_config_fails_cleanly(tmp_path: Path) -> None:
    missing = str(tmp_path / "nope.yaml")
    code = main(["search", "--config", missing], environ={"TRAVELPAYOUTS_API_TOKEN": "t"})
    assert code == 1


def test_search_runs_with_fixture() -> None:
    code = main(
        ["search", "--config", CONFIG, "--limit", "5"],
        environ={"TRAVELPAYOUTS_API_TOKEN": "t"},
        transport=fixture_transport,
        now=datetime(2026, 10, 27, 12, tzinfo=ZoneInfo("Europe/Madrid")),
    )
    assert code == 0


def test_format_candidates_empty() -> None:
    assert format_candidates([], passengers=2) == "No fares pass the filters."


def test_fixture_is_valid_json() -> None:
    assert json.loads(FIXTURE.read_text(encoding="utf-8"))["success"] is True


def api_and_telegram_transport(sent: list[dict[str, object]]):  # type: ignore[no-untyped-def]
    def transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
        if "api.telegram.org" in request.full_url:
            sent.append(json.loads(request.data))  # type: ignore[arg-type]
            return HttpResponse(200, b'{"ok": true}')
        if "/data/es/cities.json" in request.full_url:
            return HttpResponse(200, CITIES)
        return HttpResponse(200, FIXTURE.read_bytes())

    return transport


NOW = datetime(2026, 10, 27, 12, tzinfo=ZoneInfo("Europe/Madrid"))
CITIES = json.dumps([{"code": "BIO", "name": "Bilbao"}, {"code": "MIL", "name": "Milán"}]).encode()
ENV = {
    "TRAVELPAYOUTS_API_TOKEN": "t",
    "TELEGRAM_BOT_TOKEN": "123:abc",
    "TELEGRAM_FLIGHTS_CHAT_ID": "-1001",
    "TELEGRAM_FLIGHTS_BIO_TOPIC_ID": "2",
}


def test_run_sends_the_start_message(tmp_path: Path) -> None:
    sent: list[dict[str, object]] = []
    db = tmp_path / "h.sqlite3"
    code = main(
        ["run", "--config", CONFIG, "--db", str(db)],
        environ=ENV,
        transport=api_and_telegram_transport(sent),
        now=NOW,
    )
    assert code == 0
    assert len(sent) == 1
    assert sent[0]["chat_id"] == -1001 and sent[0]["message_thread_id"] == 2
    assert "Empiezo a vigilar vuelos desde Bilbao" in str(sent[0]["text"])
    assert "Milán (MXP)" in str(sent[0]["text"])
    assert db.exists()


def test_run_dry_run_needs_no_telegram_settings(tmp_path: Path) -> None:
    sent: list[dict[str, object]] = []
    code = main(
        ["run", "--config", CONFIG, "--db", str(tmp_path / "h.sqlite3"), "--dry-run"],
        environ={"TRAVELPAYOUTS_API_TOKEN": "t"},
        transport=api_and_telegram_transport(sent),
        now=NOW,
    )
    assert code == 0
    assert sent == []


def test_run_without_telegram_settings_fails_before_searching(tmp_path: Path) -> None:
    calls: list[str] = []

    def transport(request: urllib.request.Request, timeout: float) -> HttpResponse:
        calls.append(request.full_url)
        return HttpResponse(200, FIXTURE.read_bytes())

    code = main(
        ["run", "--config", CONFIG, "--db", str(tmp_path / "h.sqlite3")],
        environ={"TRAVELPAYOUTS_API_TOKEN": "t"},
        transport=transport,
        now=NOW,
    )
    assert code == 1
    assert calls == []
