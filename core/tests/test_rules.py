"""Tests for deal rule evaluation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from dealhunter_core.config import DealWindow
from dealhunter_core.rules import drop_percent, evaluate, fmt


def window(match: str = "any") -> DealWindow:
    data: dict[str, Any] = {
        "name": "regular",
        "label": "Deal",
        "min_days_ahead": 30,
        "max_days_ahead": 180,
        "match": match,
        "rules": [
            {"type": "drop_vs_usual", "min_drop_percent": 30},
            {"type": "max_price_per_person", "amount": 40},
        ],
    }
    return DealWindow.model_validate(data)


def test_fmt() -> None:
    assert fmt(Decimal("40.0")) == "40"
    assert fmt(Decimal("35.50")) == "35.5"
    assert fmt(Decimal("100")) == "100"
    assert fmt(None) == "?"


def test_drop_percent() -> None:
    assert drop_percent(Decimal("70"), Decimal("100")) == Decimal("30.0")
    assert drop_percent(Decimal("110"), Decimal("100")) == Decimal("-10.0")
    assert drop_percent(Decimal("2"), Decimal("3")) == Decimal("33.3")
    with pytest.raises(ValueError):
        drop_percent(Decimal("1"), Decimal("0"))


def test_cheap_price_without_history_is_a_deal() -> None:
    result = evaluate(window(), Decimal("40"), None)
    assert result.is_deal
    assert result.drop_percent is None
    assert result.reasons == ("at most 40 per person",)


def test_drop_rule_needs_history() -> None:
    assert not evaluate(window(), Decimal("45"), None).is_deal


def test_drop_rule_with_history() -> None:
    result = evaluate(window(), Decimal("65"), Decimal("100"))
    assert result.is_deal
    assert result.drop_percent == Decimal("35.0")
    assert result.reasons == ("35% below usual (100)",)


def test_not_a_deal() -> None:
    result = evaluate(window(), Decimal("80"), Decimal("100"))
    assert not result.is_deal
    assert result.reasons == ()
    assert result.drop_percent == Decimal("20.0")


def test_match_all_requires_every_rule() -> None:
    assert not evaluate(window("all"), Decimal("40"), Decimal("50")).is_deal
    assert evaluate(window("all"), Decimal("30"), Decimal("50")).is_deal
