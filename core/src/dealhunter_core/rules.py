"""Deal rules: is a price a deal according to its deal window?"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from dealhunter_core.config import DealWindow, DropVsUsualRule, MaxPricePerPersonRule


@dataclass(frozen=True, slots=True)
class Evaluation:
    """Result of checking one price against the rules of a window."""

    is_deal: bool
    reasons: tuple[str, ...]
    usual_price: Decimal | None
    drop_percent: Decimal | None


def fmt(value: Decimal | None) -> str:
    """Human-friendly number: ``40.0`` → ``40``, ``35.50`` → ``35.5``."""
    if value is None:
        return "?"
    return format(value.normalize(), "f")


def drop_percent(price: Decimal, usual: Decimal) -> Decimal:
    """How much cheaper ``price`` is than ``usual``, in percent (negative if dearer)."""
    if usual <= 0:
        raise ValueError("usual price must be positive")
    value = (usual - price) / usual * 100
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def evaluate(window: DealWindow, price: Decimal, usual: Decimal | None) -> Evaluation:
    """Apply the window's rules to ``price``.

    ``usual`` is the usual price of the route (``None`` without enough history, in
    which case ``drop_vs_usual`` rules simply do not match).
    """
    drop = drop_percent(price, usual) if usual is not None else None
    matched: list[str] = []
    results: list[bool] = []

    for rule in window.rules:
        if isinstance(rule, DropVsUsualRule):
            ok = drop is not None and drop >= Decimal(str(rule.min_drop_percent))
            if ok:
                matched.append(f"{fmt(drop)}% below usual ({fmt(usual)})")
        elif isinstance(rule, MaxPricePerPersonRule):
            limit = Decimal(str(rule.amount))
            ok = price <= limit
            if ok:
                matched.append(f"at most {fmt(limit)} per person")
        results.append(ok)

    is_deal = any(results) if window.match == "any" else all(results)
    return Evaluation(
        is_deal=is_deal,
        reasons=tuple(matched) if is_deal else (),
        usual_price=usual,
        drop_percent=drop,
    )
