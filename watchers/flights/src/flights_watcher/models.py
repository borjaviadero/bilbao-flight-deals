"""Domain objects of the flights watcher."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Fare:
    """A round-trip fare as returned by the price source, normalised.

    ``price_per_person`` is the round-trip price for one adult.
    """

    origin_airport: str
    destination_airport: str
    destination_city: str
    departure_at: datetime
    return_at: datetime
    price_per_person: Decimal
    currency: str
    airline: str
    flight_number: str
    stops_out: int
    stops_back: int
    duration_minutes: int
    outbound_minutes: int  # flight time of the outbound leg, a proxy for distance
    gate: str
    link: str

    @property
    def max_stops(self) -> int:
        """Stops on the leg with most stops."""
        return max(self.stops_out, self.stops_back)

    @property
    def nights(self) -> int:
        """Nights at destination (calendar days between departure and return)."""
        return (self.return_at.date() - self.departure_at.date()).days

    def days_ahead(self, today: date) -> int:
        """Days from ``today`` to the departure date."""
        return (self.departure_at.date() - today).days

    def total_price(self, passengers: int) -> Decimal:
        """Round-trip price for ``passengers`` adults."""
        return self.price_per_person * passengers

    @property
    def key(self) -> str:
        """Identity of the trip (route, dates and carrier), used to de-duplicate."""
        return "|".join(
            (
                self.origin_airport,
                self.destination_airport,
                self.departure_at.date().isoformat(),
                self.return_at.date().isoformat(),
                self.airline,
            )
        )


@dataclass(frozen=True, slots=True)
class Candidate:
    """A fare that passed the filters, with the deal window its departure falls into."""

    fare: Fare
    window: str
    days_ahead: int
