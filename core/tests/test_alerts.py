"""Tests for alert planning: repeats, ranking and the per-run cap."""

from __future__ import annotations

from decimal import Decimal

from dealhunter_core.alerts import Opportunity, plan_alerts
from dealhunter_core.rules import Evaluation


def opp(key: str, price: str, drop: str | None = None) -> Opportunity[str]:
    evaluation = Evaluation(
        is_deal=True,
        reasons=("test",),
        usual_price=None,
        drop_percent=Decimal(drop) if drop is not None else None,
    )
    return Opportunity(
        item_key=key, price=Decimal(price), window="w", evaluation=evaluation, item=key
    )


def test_skips_repeats_unless_cheaper() -> None:
    previous = {"same": Decimal("40"), "higher": Decimal("40"), "lower": Decimal("40")}
    plan = plan_alerts(
        [opp("same", "40"), opp("higher", "45"), opp("lower", "35"), opp("new", "39")],
        last_alert_price=previous.get,
        repeat_only_if_lower=True,
        max_per_run=10,
    )
    assert sorted(o.item_key for o in plan.send) == ["lower", "new"]
    assert sorted(o.item_key for o in plan.skipped) == ["higher", "same"]


def test_never_repeat_when_disabled() -> None:
    plan = plan_alerts(
        [opp("lower", "35")],
        last_alert_price={"lower": Decimal("40")}.get,
        repeat_only_if_lower=False,
        max_per_run=10,
    )
    assert plan.send == []
    assert [o.item_key for o in plan.skipped] == ["lower"]


def test_ranking_and_cap() -> None:
    opportunities = [
        opp("cheap-no-history", "20"),
        opp("big-drop", "60", drop="45"),
        opp("small-drop", "50", drop="31"),
        opp("cheaper-no-history", "15"),
        opp("mid", "30"),
    ]
    plan = plan_alerts(
        opportunities, last_alert_price=lambda _: None, repeat_only_if_lower=True, max_per_run=3
    )
    assert [o.item_key for o in plan.send] == ["big-drop", "small-drop", "cheaper-no-history"]
    assert [o.item_key for o in plan.summary] == ["cheap-no-history", "mid"]
    assert plan.skipped == []
