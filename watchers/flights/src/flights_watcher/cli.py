"""Command-line interface: ``python -m flights_watcher <command>``.

Commands:
    search   Fetch fares for an instance and list those that pass the filters.
             Read-only: stores nothing and sends no alerts.
"""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dealhunter_core.config import ConfigError, require_env
from dealhunter_core.http import HttpError, JsonHttpClient, Transport, urllib_transport
from flights_watcher.config import load_config
from flights_watcher.models import Candidate
from flights_watcher.price_api import PriceApiError, TravelpayoutsClient
from flights_watcher.search import fetch_fares, select_candidates

logger = logging.getLogger("flights_watcher")

TIMEZONE = ZoneInfo("Europe/Madrid")
TOKEN_ENV = "TRAVELPAYOUTS_API_TOKEN"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flights-watcher", description="Look for round-trip flight deals."
    )
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING… (default INFO)")
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser(
        "search", help="list fares that pass the filters (read-only, sends nothing)"
    )
    search.add_argument("--config", type=Path, required=True, help="instance YAML file")
    search.add_argument("--limit", type=int, default=20, help="rows to show (default 20)")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    transport: Transport = urllib_transport,
    today: date | None = None,
) -> int:
    """Entry point. Returns the process exit code (0 = success)."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    env = os.environ if environ is None else environ
    day = today or datetime.now(TIMEZONE).date()

    try:
        config = load_config(args.config)
        client = TravelpayoutsClient(
            require_env(TOKEN_ENV, env), JsonHttpClient(transport=transport)
        )
        fares = fetch_fares(config, client, day)
        candidates = select_candidates(fares, config, day)
    except (ConfigError, HttpError, PriceApiError) as exc:
        logger.error("%s", exc)
        return 1

    print(format_candidates(candidates[: args.limit], passengers=config.search.passengers))
    print(
        f"\n{len(fares)} fares fetched · {len(candidates)} pass the filters "
        f"(max {config.search.max_stops} stop(s), {config.min_days_ahead}-"
        f"{config.max_days_ahead} days ahead) · showing {min(args.limit, len(candidates))}"
    )
    return 0


def format_candidates(candidates: Sequence[Candidate], *, passengers: int) -> str:
    """Plain-text table of candidates, cheapest first."""
    if not candidates:
        return "No fares pass the filters."

    header = (
        "WINDOW",
        "OUT",
        "BACK",
        "NIGHTS",
        "TO",
        "AIRLINE",
        "STOPS",
        "PER PERSON",
        f"TOTAL x{passengers}",
        "DAYS AHEAD",
    )
    rows = [header]
    for c in candidates:
        f = c.fare
        rows.append(
            (
                c.window,
                f.departure_at.strftime("%Y-%m-%d"),
                f.return_at.strftime("%Y-%m-%d"),
                str(f.nights),
                f"{f.destination_airport} ({f.destination_city})",
                f.airline,
                f"{f.stops_out}/{f.stops_back}",
                f"{f.price_per_person} {f.currency}",
                f"{f.total_price(passengers)} {f.currency}",
                str(c.days_ahead),
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    return "\n".join(
        "  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)).rstrip()
        for row in rows
    )
