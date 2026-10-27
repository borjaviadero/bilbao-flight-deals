"""Configuration of a flights watcher instance (e.g. ``config/watchers/flights-bio.yaml``)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from dealhunter_core.config import InstanceConfig, StrictModel, load_instance_config

IataCode = str  # three upper-case letters, validated by the field patterns below


class FlightSearch(StrictModel):
    """What to search for. Prices from the API are per adult."""

    origin: IataCode = Field(pattern=r"^[A-Z]{3}$")
    destinations: Literal["any"] | list[IataCode] = "any"
    trip: Literal["round_trip"] = "round_trip"
    passengers: int = Field(ge=1, le=9)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    trip_length_nights: Literal["any"] = "any"
    max_stops: int = Field(ge=0, le=2, description="Maximum stops on each leg")


class FlightsInstanceConfig(InstanceConfig):
    """A flights instance: the shared sections plus ``search``."""

    watcher: Literal["flights"]
    search: FlightSearch


def load_config(path: Path) -> FlightsInstanceConfig:
    """Load and validate a flights instance file."""
    return load_instance_config(path, FlightsInstanceConfig)
