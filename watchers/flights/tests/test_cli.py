"""Tests for the command-line interface."""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path

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
        today=date(2026, 10, 27),
    )
    assert code == 0


def test_format_candidates_empty() -> None:
    assert format_candidates([], passengers=2) == "No fares pass the filters."


def test_fixture_is_valid_json() -> None:
    assert json.loads(FIXTURE.read_text(encoding="utf-8"))["success"] is True
