"""Instance configuration shared by every watcher.

An *instance* is one YAML file in ``config/watchers/`` (for example ``flights-bio.yaml``).
The sections that every watcher has in common are validated here: schedule, deal windows,
alert settings and the Telegram target. Each watcher subclasses :class:`InstanceConfig`
to add its own ``search`` section.

Validation is strict: unknown keys are rejected, so a typo in the YAML fails loudly
instead of being silently ignored.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ConfigError(Exception):
    """Raised when a configuration file or a required environment variable is invalid."""


class StrictModel(BaseModel):
    """Base model: immutable and rejecting unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Deal rules ----------------------------------------------------------------


class DropVsUsualRule(StrictModel):
    """Deal if the price is at least ``min_drop_percent`` below the usual price.

    The usual price is the median of the prices seen for the same route in the last
    ``lookback_days``. With fewer than ``min_observations`` the rule does not apply.
    """

    type: Literal["drop_vs_usual"]
    min_drop_percent: float = Field(gt=0, lt=100)
    lookback_days: int = Field(default=30, ge=1)
    min_observations: int = Field(default=5, ge=1)


class MaxPricePerPersonRule(StrictModel):
    """Deal if the price per person is at most ``amount``."""

    type: Literal["max_price_per_person"]
    amount: float = Field(gt=0)


DealRule = Annotated[DropVsUsualRule | MaxPricePerPersonRule, Field(discriminator="type")]


class DealWindow(StrictModel):
    """A range of days ahead (from today to departure) with its own deal rules."""

    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    min_days_ahead: int = Field(ge=0)
    max_days_ahead: int = Field(ge=0)
    match: Literal["any", "all"] = "any"
    rules: list[DealRule] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.min_days_ahead > self.max_days_ahead:
            raise ValueError(
                f"window '{self.name}': min_days_ahead ({self.min_days_ahead}) "
                f"is greater than max_days_ahead ({self.max_days_ahead})"
            )
        return self

    def contains(self, days_ahead: int) -> bool:
        """Whether a departure ``days_ahead`` days from today falls in this window."""
        return self.min_days_ahead <= days_ahead <= self.max_days_ahead

    @property
    def drop_rule(self) -> DropVsUsualRule | None:
        """The window's ``drop_vs_usual`` rule, if it has one."""
        return next((r for r in self.rules if isinstance(r, DropVsUsualRule)), None)


# --- Alerts and Telegram -----------------------------------------------------------

Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class AlertSettings(StrictModel):
    """How alerts are sent."""

    repeat_only_if_lower: bool = True
    max_per_run: int = Field(
        default=5, ge=1, description="Alerts per run; the rest go in a summary"
    )
    warmup_first_run: bool = Field(
        default=True, description="First run only records prices and sends a start message"
    )
    weekly_summary: Weekday | None = None


class ResolvedTelegramTarget(StrictModel):
    """Telegram destination with the IDs already read from the environment."""

    chat_id: int
    topic_id: int


class TelegramTarget(StrictModel):
    """Where an instance posts its alerts.

    The IDs are deployment-specific, so the config only names the environment
    variables that hold them.
    """

    group: str
    topic: str
    chat_id_env: str
    topic_id_env: str

    def resolve(self, environ: Mapping[str, str] | None = None) -> ResolvedTelegramTarget:
        """Read the chat and topic IDs from the environment."""
        env = os.environ if environ is None else environ
        return ResolvedTelegramTarget(
            chat_id=_int_env(self.chat_id_env, env),
            topic_id=_int_env(self.topic_id_env, env),
        )


# --- Instance ------------------------------------------------------------------


class InstanceConfig(StrictModel):
    """Settings shared by every watcher instance. Watchers extend it with ``search``."""

    watcher: str
    instance: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    enabled: bool = True
    schedule: str = Field(min_length=1, description="Cron expression")
    deal_windows: list[DealWindow] = Field(min_length=1)
    alerts: AlertSettings
    telegram: TelegramTarget

    @model_validator(mode="after")
    def _check_windows(self) -> Self:
        names = [window.name for window in self.deal_windows]
        if len(names) != len(set(names)):
            raise ValueError(f"deal window names must be unique, got {names}")

        ordered = sorted(self.deal_windows, key=lambda window: window.min_days_ahead)
        for previous, current in pairwise(ordered):
            if current.min_days_ahead <= previous.max_days_ahead:
                raise ValueError(f"deal windows '{previous.name}' and '{current.name}' overlap")
        return self

    @property
    def min_days_ahead(self) -> int:
        """Earliest departure, in days ahead, covered by any window."""
        return min(window.min_days_ahead for window in self.deal_windows)

    @property
    def max_days_ahead(self) -> int:
        """Latest departure, in days ahead, covered by any window."""
        return max(window.max_days_ahead for window in self.deal_windows)

    def window_named(self, name: str) -> DealWindow:
        """The deal window called ``name`` (raises ``KeyError`` if there is none)."""
        for window in self.deal_windows:
            if window.name == name:
                return window
        raise KeyError(name)

    def window_for(self, days_ahead: int) -> DealWindow | None:
        """The deal window a departure falls into, or ``None`` if it is out of range."""
        return next((w for w in self.deal_windows if w.contains(days_ahead)), None)


def load_instance_config[ConfigT: InstanceConfig](path: Path, model: type[ConfigT]) -> ConfigT:
    """Load and validate an instance YAML file with the given config model."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"{path}: invalid configuration\n{exc}") from exc


def require_env(name: str, environ: Mapping[str, str] | None = None) -> str:
    """Return a required environment variable, failing clearly if it is missing or empty."""
    env = os.environ if environ is None else environ
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"environment variable {name} is not set (see .env.example)")
    return value


def _int_env(name: str, environ: Mapping[str, str]) -> int:
    value = require_env(name, environ)
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"environment variable {name} must be an integer") from exc
