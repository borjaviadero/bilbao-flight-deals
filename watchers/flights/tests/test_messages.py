"""Tests for the Telegram message texts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from dealhunter_core.alerts import Opportunity
from dealhunter_core.rules import Evaluation
from flights_watcher.config import FlightsInstanceConfig, load_config
from flights_watcher.messages import (
    _truncate,
    alert_message,
    short_date,
    start_message,
    summary_message,
)
from flights_watcher.models import Candidate, Fare

REPO_ROOT = Path(__file__).resolve().parents[3]
FARE = Fare(
    origin_airport="BIO",
    destination_airport="MXP",
    destination_city="MIL",
    departure_at=datetime(2026, 12, 10, 8, 0),
    return_at=datetime(2026, 12, 14, 20, 0),
    price_per_person=Decimal("30"),
    currency="EUR",
    airline="VY",
    flight_number="1",
    stops_out=0,
    stops_back=0,
    duration_minutes=240,
    gate="g",
    link="https://www.aviasales.com/search/X?a=1&b=2",
)


def config() -> FlightsInstanceConfig:
    return load_config(REPO_ROOT / "config" / "watchers" / "flights-bio.yaml")


def opportunity(drop: str | None = None, **fare_changes: object) -> Opportunity[Candidate]:
    fare = replace(FARE, **fare_changes)  # type: ignore[arg-type]
    evaluation = Evaluation(
        is_deal=True,
        reasons=(),
        usual_price=Decimal("100") if drop else None,
        drop_percent=Decimal(drop) if drop else None,
    )
    return Opportunity(
        item_key=fare.key,
        price=fare.price_per_person,
        window="regular",
        evaluation=evaluation,
        item=Candidate(fare=fare, window="regular", days_ahead=44),
    )


def test_short_date() -> None:
    assert short_date(datetime(2026, 12, 10), "es") == "jue 10 dic"
    assert short_date(datetime(2026, 12, 10), "en") == "Thu 10 Dec"


def test_alert_message_spanish() -> None:
    text = alert_message(opportunity(drop="70"), config(), "es")
    assert text.splitlines() == [
        "<b>✈️ Chollo · BIO → MXP (MIL)</b>",
        "📅 jue 10 dic → lun 14 dic · 4 noches",
        "🛫 Directo ida y vuelta · VY",
        "💶 30 € por persona · 60 € para 2",
        "📉 70% por debajo de lo habitual (100 €)",
        "⏳ Sale dentro de 44 días",
        '<a href="https://www.aviasales.com/search/X?a=1&amp;b=2">Ver vuelo</a>',
    ]


def test_alert_message_english_with_stops_and_no_history() -> None:
    text = alert_message(opportunity(stops_back=1), config(), "en")
    assert "<b>✈️ Deal · BIO → MXP (MIL)</b>" in text
    assert "Stops: 0 out · 1 back" in text
    assert "below usual" not in text


def test_values_are_escaped() -> None:
    text = alert_message(opportunity(airline="<script>"), config(), "en")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_summary_message() -> None:
    text = summary_message([opportunity(), opportunity(destination_airport="STN")], "es")
    lines = text.splitlines()
    assert lines[0] == "<b>📋 2 chollos más en esta búsqueda</b>"
    assert lines[2].startswith('• <a href="') and "STN · jue 10 dic → lun 14 dic · 30 €" in lines[2]
    assert summary_message([opportunity()], "es").startswith("<b>📋 1 chollo más en")


def test_start_message() -> None:
    candidates = [opportunity().item]
    text = start_message(config(), candidates, recorded=194, language="es")
    assert "Empiezo a vigilar vuelos desde BIO" in text
    assert "de 7 a 180 días vista, máx. 1 escala(s)" in text
    assert "194 precios guardados" in text
    assert "MXP · jue 10 dic" in text
    assert "ningún vuelo" in start_message(config(), [], recorded=0, language="es")


def test_truncate_keeps_whole_lines() -> None:
    text = "\n".join(f"line {n}" for n in range(1000))
    result = _truncate(text, limit=100)
    assert len(result) <= 100
    assert result.endswith("\n…")
    assert all(line.startswith("line") for line in result.splitlines()[:-1])
