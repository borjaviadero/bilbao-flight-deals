"""Price history and alert log, stored in SQLite.

Generic for every watcher: items and routes are identified by string keys that each
watcher builds (for flights, ``item_key`` is one trip and ``route_key`` is
origin-destination).

Tables:
    runs          one row per execution of an instance (used for the warm-up run)
    observations  every price seen, per item and route
    alerts        the last alert sent per item (to avoid repeating alerts)

Prices are stored as text to keep ``Decimal`` precision; timestamps are UTC ISO 8601.
"""

from __future__ import annotations

import sqlite3
import statistics
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from typing import Self

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    instance      TEXT    NOT NULL,
    started_at    TEXT    NOT NULL,
    finished_at   TEXT,
    fetched       INTEGER,
    candidates    INTEGER,
    alerts_sent   INTEGER,
    warmup        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS observations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    instance      TEXT    NOT NULL,
    item_key      TEXT    NOT NULL,
    route_key     TEXT    NOT NULL,
    price         TEXT    NOT NULL,
    currency      TEXT    NOT NULL,
    observed_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_observations_route
    ON observations (instance, route_key, observed_at);

CREATE TABLE IF NOT EXISTS alerts (
    instance      TEXT    NOT NULL,
    item_key      TEXT    NOT NULL,
    price         TEXT    NOT NULL,
    window        TEXT    NOT NULL,
    alerted_at    TEXT    NOT NULL,
    PRIMARY KEY (instance, item_key)
);
"""


@dataclass(frozen=True, slots=True)
class Observation:
    """One price seen for one item."""

    item_key: str
    route_key: str
    price: Decimal
    currency: str


class PriceHistory:
    """Access to the SQLite history of one database file."""

    def __init__(self, path: Path | str) -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)

    @classmethod
    def in_memory(cls) -> PriceHistory:
        """A throw-away database, for tests and dry runs."""
        return cls(":memory:")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._conn:  # commits on success, rolls back on error
            yield self._conn

    # --- runs --------------------------------------------------------------------

    def completed_runs(self, instance: str) -> int:
        """How many runs of ``instance`` finished successfully."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM runs WHERE instance = ? AND finished_at IS NOT NULL",
            (instance,),
        ).fetchone()
        return int(row[0])

    def start_run(self, instance: str, now: datetime) -> int:
        with self._transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (instance, started_at) VALUES (?, ?)",
                (instance, _ts(now)),
            )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def finish_run(
        self,
        run_id: int,
        now: datetime,
        *,
        fetched: int,
        candidates: int,
        alerts_sent: int,
        warmup: bool,
    ) -> None:
        with self._transaction() as conn:
            conn.execute(
                "UPDATE runs SET finished_at = ?, fetched = ?, candidates = ?, alerts_sent = ?,"
                " warmup = ? WHERE id = ?",
                (_ts(now), fetched, candidates, alerts_sent, int(warmup), run_id),
            )

    # --- observations ------------------------------------------------------------

    def record(self, instance: str, observations: Iterable[Observation], now: datetime) -> int:
        """Store every observation of a run. Returns how many were stored."""
        rows = [
            (instance, o.item_key, o.route_key, str(o.price), o.currency, _ts(now))
            for o in observations
        ]
        with self._transaction() as conn:
            conn.executemany(
                "INSERT INTO observations"
                " (instance, item_key, route_key, price, currency, observed_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def usual_price(
        self, instance: str, route_key: str, *, since: datetime, min_observations: int
    ) -> Decimal | None:
        """Median price of a route since ``since``, or ``None`` with too little data."""
        prices = [
            Decimal(row[0])
            for row in self._conn.execute(
                "SELECT price FROM observations"
                " WHERE instance = ? AND route_key = ? AND observed_at >= ?",
                (instance, route_key, _ts(since)),
            )
        ]
        if len(prices) < min_observations:
            return None
        return Decimal(statistics.median(prices))

    # --- alerts --------------------------------------------------------------------

    def last_alert_price(self, instance: str, item_key: str) -> Decimal | None:
        row = self._conn.execute(
            "SELECT price FROM alerts WHERE instance = ? AND item_key = ?",
            (instance, item_key),
        ).fetchone()
        return Decimal(row[0]) if row else None

    def record_alert(
        self, instance: str, item_key: str, price: Decimal, window: str, now: datetime
    ) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO alerts (instance, item_key, price, window, alerted_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (instance, item_key) DO UPDATE SET"
                " price = excluded.price, window = excluded.window,"
                " alerted_at = excluded.alerted_at",
                (instance, item_key, str(price), window, _ts(now)),
            )


def _ts(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return moment.astimezone(UTC).isoformat(timespec="seconds")
