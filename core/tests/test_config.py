"""Tests for the shared instance configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dealhunter_core.config import (
    ConfigError,
    DealWindow,
    InstanceConfig,
    TelegramTarget,
    load_instance_config,
    require_env,
)


def window(name: str, low: int, high: int) -> dict[str, Any]:
    return {
        "name": name,
        "label": name,
        "min_days_ahead": low,
        "max_days_ahead": high,
        "rules": [{"type": "max_price_per_person", "amount": 50}],
    }


def instance(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "watcher": "test",
        "instance": "test-one",
        "schedule": "0 */6 * * *",
        "deal_windows": [window("regular", 30, 180), window("last_minute", 7, 29)],
        "alerts": {"repeat_only_if_lower": True, "weekly_summary": "sunday"},
        "telegram": {
            "group": "g",
            "topic": "t",
            "chat_id_env": "CHAT",
            "topic_id_env": "TOPIC",
        },
    }
    data.update(overrides)
    return data


class TestDealWindow:
    def test_contains_is_inclusive(self) -> None:
        w = DealWindow.model_validate(window("w", 7, 29))
        assert w.contains(7)
        assert w.contains(29)
        assert not w.contains(6)
        assert not w.contains(30)

    def test_rejects_inverted_range(self) -> None:
        with pytest.raises(ValueError, match="greater than"):
            DealWindow.model_validate(window("w", 30, 7))

    def test_rejects_unknown_rule_type(self) -> None:
        data = window("w", 1, 2)
        data["rules"] = [{"type": "made_up", "amount": 1}]
        with pytest.raises(ValueError):
            DealWindow.model_validate(data)


class TestInstanceConfig:
    def test_valid_config(self) -> None:
        cfg = InstanceConfig.model_validate(instance())
        assert cfg.min_days_ahead == 7
        assert cfg.max_days_ahead == 180

    def test_window_for(self) -> None:
        cfg = InstanceConfig.model_validate(instance())
        assert cfg.window_for(10) is not None
        assert cfg.window_for(10).name == "last_minute"  # type: ignore[union-attr]
        assert cfg.window_for(45).name == "regular"  # type: ignore[union-attr]
        assert cfg.window_for(3) is None
        assert cfg.window_for(181) is None

    def test_rejects_overlapping_windows(self) -> None:
        data = instance(deal_windows=[window("a", 7, 30), window("b", 30, 180)])
        with pytest.raises(ValueError, match="overlap"):
            InstanceConfig.model_validate(data)

    def test_rejects_duplicate_window_names(self) -> None:
        data = instance(deal_windows=[window("a", 7, 29), window("a", 30, 180)])
        with pytest.raises(ValueError, match="unique"):
            InstanceConfig.model_validate(data)

    def test_rejects_unknown_keys(self) -> None:
        with pytest.raises(ValueError, match="extra"):
            InstanceConfig.model_validate(instance(typo_key=1))

    def test_rejects_bad_instance_name(self) -> None:
        with pytest.raises(ValueError):
            InstanceConfig.model_validate(instance(instance="Bad Name"))


class TestTelegramTarget:
    target = TelegramTarget(group="g", topic="t", chat_id_env="CHAT", topic_id_env="TOPIC")

    def test_resolve_reads_env(self) -> None:
        resolved = self.target.resolve({"CHAT": "-1001", "TOPIC": "2"})
        assert resolved.chat_id == -1001
        assert resolved.topic_id == 2

    def test_resolve_missing_env(self) -> None:
        with pytest.raises(ConfigError, match="CHAT"):
            self.target.resolve({"TOPIC": "2"})

    def test_resolve_non_integer(self) -> None:
        with pytest.raises(ConfigError, match="integer"):
            self.target.resolve({"CHAT": "abc", "TOPIC": "2"})


class TestHelpers:
    def test_require_env(self) -> None:
        assert require_env("X", {"X": " value "}) == "value"
        with pytest.raises(ConfigError):
            require_env("X", {"X": "  "})

    def test_load_instance_config_errors(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.yaml"
        with pytest.raises(ConfigError, match="cannot read"):
            load_instance_config(missing, InstanceConfig)

        not_mapping = tmp_path / "list.yaml"
        not_mapping.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="mapping"):
            load_instance_config(not_mapping, InstanceConfig)

        invalid = tmp_path / "invalid.yaml"
        invalid.write_text("watcher: x\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="invalid configuration"):
            load_instance_config(invalid, InstanceConfig)
