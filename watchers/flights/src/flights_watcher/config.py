"""Configuration of a flights watcher instance (e.g. ``config/watchers/flights-bio.yaml``)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from dealhunter_core.config import InstanceConfig, StrictModel, load_instance_config

IataCode = str  # three upper-case letters, validated by the field patterns below


class TripLengthRule(StrictModel):
    """Nights allowed for trips whose outbound flight lasts up to ``max_flight_hours``.

    The rule without ``max_flight_hours`` applies to every longer flight.
    """

    max_flight_hours: float | None = Field(default=None, gt=0)
    min_nights: int = Field(ge=0)
    max_nights: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_nights(self) -> Self:
        if self.min_nights > self.max_nights:
            raise ValueError(f"min_nights ({self.min_nights}) > max_nights ({self.max_nights})")
        return self

    def covers(self, outbound_minutes: int) -> bool:
        return self.max_flight_hours is None or outbound_minutes <= self.max_flight_hours * 60


class FlightSearch(StrictModel):
    """What to search for. Prices from the API are per adult."""

    origin: IataCode = Field(pattern=r"^[A-Z]{3}$")
    destinations: Literal["any"] | list[IataCode] = "any"
    trip: Literal["round_trip"] = "round_trip"
    passengers: int = Field(ge=1, le=9)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    trip_length: list[TripLengthRule] = Field(
        default_factory=list, description="Nights allowed by flight time; empty = any length"
    )
    max_stops: int = Field(ge=0, le=2, description="Maximum stops on each leg")
    city_names: dict[IataCode, str] = Field(
        default_factory=dict,
        description="Names that replace the downloaded ones, by IATA city or airport code",
    )

    @model_validator(mode="after")
    def _check_trip_length(self) -> Self:
        hours = [r.max_flight_hours for r in self.trip_length]
        bounded = [h for h in hours if h is not None]
        if bounded != sorted(bounded) or len(set(bounded)) != len(bounded):
            raise ValueError("trip_length rules must have increasing max_flight_hours")
        if None in hours and hours.index(None) != len(hours) - 1:
            raise ValueError("the trip_length rule without max_flight_hours must be the last one")
        return self

    def nights_allowed(self, outbound_minutes: int, nights: int) -> bool:
        """Whether a trip of ``nights`` fits the rule for its outbound flight time."""
        if not self.trip_length:
            return True
        rule = next((r for r in self.trip_length if r.covers(outbound_minutes)), None)
        return rule is not None and rule.min_nights <= nights <= rule.max_nights


class FlightsInstanceConfig(InstanceConfig):
    """A flights instance: the shared sections plus ``search``."""

    watcher: Literal["flights"]
    search: FlightSearch


def load_config(path: Path) -> FlightsInstanceConfig:
    """Load and validate a flights instance file."""
    return load_instance_config(path, FlightsInstanceConfig)
