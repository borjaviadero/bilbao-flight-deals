"""Tests for the flights instance configuration, including the real config files."""

from __future__ import annotations

from pathlib import Path

import pytest

from dealhunter_core.config import ConfigError, MaxPricePerPersonRule
from flights_watcher.config import FlightSearch, TripLengthRule, load_config

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
    assert MaxPricePerPersonRule(type="max_price_per_person", amount=40) in regular.rules
    assert cfg.alerts.max_per_run == 5
    assert cfg.alerts.warmup_first_run is True
    drop = regular.drop_rule
    assert drop is not None and (drop.lookback_days, drop.min_observations) == (30, 5)


def test_rejects_invalid_origin(tmp_path: Path) -> None:
    text = (CONFIG_DIR / "flights-bio.yaml").read_text(encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(text.replace("origin: BIO", "origin: bilbao"), encoding="utf-8")
    with pytest.raises(ConfigError, match="origin"):
        load_config(bad)


class TestTripLength:
    def search(self) -> FlightSearch:
        return load_config(CONFIG_DIR / "flights-bio.yaml").search

    def test_flights_bio_rules(self) -> None:
        s = self.search()
        # up to 3 h: 2-7 nights
        assert s.nights_allowed(120, 7)
        assert not s.nights_allowed(120, 8)
        assert not s.nights_allowed(120, 1)
        # 3-6 h: 3-10 nights
        assert s.nights_allowed(240, 10)
        assert not s.nights_allowed(240, 2)
        # longer: 6-21 nights
        assert s.nights_allowed(700, 21)
        assert not s.nights_allowed(700, 5)

    def test_empty_means_any_length(self) -> None:
        s = self.search().model_copy(update={"trip_length": []})
        assert s.nights_allowed(120, 30)

    def test_without_catch_all_long_flights_are_dropped(self) -> None:
        rule = TripLengthRule(max_flight_hours=3, min_nights=2, max_nights=7)
        data = self.search().model_dump()
        data["trip_length"] = [rule.model_dump()]
        s = FlightSearch.model_validate(data)
        assert not s.nights_allowed(400, 5)

    @pytest.mark.parametrize(
        "rules",
        [
            [
                {"max_flight_hours": 6, "min_nights": 1, "max_nights": 2},
                {"max_flight_hours": 3, "min_nights": 1, "max_nights": 2},
            ],
            [
                {"min_nights": 1, "max_nights": 2},
                {"max_flight_hours": 3, "min_nights": 1, "max_nights": 2},
            ],
            [{"max_flight_hours": 3, "min_nights": 5, "max_nights": 2}],
        ],
    )
    def test_invalid_rules(self, rules: list[dict[str, float]]) -> None:
        data = self.search().model_dump()
        data["trip_length"] = rules
        with pytest.raises(ValueError):
            FlightSearch.model_validate(data)
