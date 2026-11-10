"""Configuration of a flights watcher instance (e.g. ``config/watchers/flights-bio.yaml``)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from dealhunter_core.config import InstanceConfig, Language, StrictModel, load_instance_config

IataCode = str  # three upper-case letters, validated by the field patterns below
UsualPriceBy = Literal["route", "route_month"]  # how prices are grouped for the usual price


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
    min_distance_km: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Only destinations at least this far, great-circle (e.g. 4500 = long haul). "
            "Flight time is not used for this: with a stop it includes the layover."
        ),
    )
    exclude_countries: list[str] = Field(
        default_factory=list,
        description="ISO country codes never alerted, e.g. [ES] for international trips only",
    )
    usual_price_by: UsualPriceBy = Field(
        default="route",
        description=(
            "Group for the usual price: the route over all dates, or the route per "
            "departure month (better where prices are seasonal, e.g. long haul)"
        ),
    )
    direct_only_countries: list[str] = Field(
        default_factory=list,
        description="ISO country codes where only direct flights (both legs) are wanted",
    )
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


class SuperDealRule(StrictModel):
    """When a deal is a super deal: posted to the group's General topic, not the city topic.

    A deal qualifies through either path:
      - price:  ``max_price_per_person`` or less; or
      - drop:   at least ``min_drop_percent`` below the usual price AND a saving of at least
                ``min_saving_per_person``, with the usual price based on at least
                ``min_observations`` prices (more than an ordinary deal needs).
    In both cases the itinerary must be reasonable: each leg with a stop may last at most
    ``max_detour_factor`` times the estimated direct flight time (from the distance).
    """

    label: str | dict[Language, str]
    max_price_per_person: Decimal | None = Field(default=None, gt=0)
    min_drop_percent: Decimal | None = Field(default=None, gt=0, le=100)
    min_saving_per_person: Decimal = Field(default=Decimal(0), ge=0)
    min_observations: int = Field(default=10, ge=1)
    max_detour_factor: float = Field(default=1.75, ge=1)
    topic_id_env: str | None = Field(
        default=None, description="Env var with the topic ID; None posts to the General topic"
    )

    @model_validator(mode="after")
    def _check_paths(self) -> Self:
        if self.max_price_per_person is None and self.min_drop_percent is None:
            raise ValueError("set max_price_per_person, min_drop_percent or both")
        return self

    def label_for(self, language: Language) -> str:
        if isinstance(self.label, str):
            return self.label
        return self.label.get(language) or self.label.get("en") or "Super deal"


class FlightsInstanceConfig(InstanceConfig):
    """A flights instance: the shared sections plus ``search`` and ``super_deals``."""

    watcher: Literal["flights"]
    search: FlightSearch
    super_deals: SuperDealRule | None = None


def load_config(path: Path) -> FlightsInstanceConfig:
    """Load and validate a flights instance file."""
    return load_instance_config(path, FlightsInstanceConfig)
