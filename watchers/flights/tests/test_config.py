"""Tests for the flights instance configuration, including the real config files."""

from __future__ import annotations

from pathlib import Path

import pytest

from dealhunter_core.config import ConfigError, MaxPricePerPersonRule
from flights_watcher.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config" / "watchers"


@pytest.mark.parametrize("path", sorted(CONFIG_DIR.glob("flights-*.yaml")), ids=lambda p: p.name)
def test_every_flights_config_is_valid(path: Path) -> None:
    cfg = load_config(path)
    assert cfg.watcher == "flights"
    assert path.stem == cfg.instance


def test_flights_bio_values() -> None:
    cfg = load_config(CONFIG_DIR / "flights-bio.yaml")
    assert cfg.search.origin == "BIO"
    assert cfg.search.passengers == 2
    assert cfg.search.max_stops == 1
    assert (cfg.min_days_ahead, cfg.max_days_ahead) == (7, 180)

    regular = cfg.window_for(45)
    last_minute = cfg.window_for(10)
    assert regular is not None and regular.name == "regular"
    assert last_minute is not None and last_minute.name == "last_minute"
    assert MaxPricePerPersonRule(type="max_price_per_person", amount=30) in last_minute.rules


def test_rejects_invalid_origin(tmp_path: Path) -> None:
    text = (CONFIG_DIR / "flights-bio.yaml").read_text(encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(text.replace("origin: BIO", "origin: bilbao"), encoding="utf-8")
    with pytest.raises(ConfigError, match="origin"):
        load_config(bad)
