"""Command-line interface: ``python -m flights_watcher <command>``.

Commands:
    search   Fetch fares for an instance and list those that pass the filters.
             Read-only: stores nothing and sends no alerts.
    run      One complete run: search, evaluate deals, record history and send
             Telegram messages. ``--dry-run`` prints the messages instead and
             writes nothing.
"""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dealhunter_core.config import ConfigError, require_env
from dealhunter_core.history import PriceHistory
from dealhunter_core.http import HttpError, JsonHttpClient, Transport, urllib_transport
from dealhunter_core.telegram import TelegramError, TelegramNotifier
from flights_watcher.config import load_config
from flights_watcher.models import Candidate
from flights_watcher.places import city_countries
from flights_watcher.price_api import PriceApiError, TravelpayoutsClient
from flights_watcher.runner import Sender, run_instance
from flights_watcher.search import fetch_fares, select_candidates

logger = logging.getLogger("flights_watcher")

TIMEZONE = ZoneInfo("Europe/Madrid")
TOKEN_ENV = "TRAVELPAYOUTS_API_TOKEN"
BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
DB_ENV = "DEALHUNTER_DB_PATH"
DEFAULT_DB = Path("data/dealhunter.sqlite3")


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

    run = commands.add_parser("run", help="search, evaluate, record and send alerts")
    run.add_argument("--config", type=Path, required=True, help="instance YAML file")
    run.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"SQLite file (default: ${DB_ENV} or {DEFAULT_DB})",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="print the messages instead of sending them; write nothing",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    transport: Transport = urllib_transport,
    now: datetime | None = None,
) -> int:
    """Entry point. Returns the process exit code (0 = success)."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    env = os.environ if environ is None else environ
    moment = now or datetime.now(TIMEZONE)

    try:
        if args.command == "search":
            return _search(args, env, transport, moment)
        return _run(args, env, transport, moment)
    except (ConfigError, HttpError, PriceApiError, TelegramError) as exc:
        logger.error("%s", exc)
        return 1


def _search(
    args: argparse.Namespace, env: Mapping[str, str], transport: Transport, now: datetime
) -> int:
    config = load_config(args.config)
    http = JsonHttpClient(transport=transport)
    client = TravelpayoutsClient(require_env(TOKEN_ENV, env), http)
    today = now.astimezone(TIMEZONE).date()
    fares = fetch_fares(config, client, today)
    countries: dict[str, str] = {}
    if config.search.direct_only_countries:
        with PriceHistory.in_memory() as scratch:  # read-only command: nothing is kept
            countries = city_countries(http, scratch, now)
    candidates = select_candidates(fares, config, today, countries)

    print(format_candidates(candidates[: args.limit], passengers=config.search.passengers))
    print(
        f"\n{len(fares)} fares fetched · {len(candidates)} pass the filters "
        f"(max {config.search.max_stops} stop(s), {config.min_days_ahead}-"
        f"{config.max_days_ahead} days ahead) · showing {min(args.limit, len(candidates))}"
    )
    return 0


def _run(
    args: argparse.Namespace, env: Mapping[str, str], transport: Transport, now: datetime
) -> int:
    config = load_config(args.config)
    http = JsonHttpClient(transport=transport)
    client = TravelpayoutsClient(require_env(TOKEN_ENV, env), http)

    send: Sender
    if args.dry_run:
        send = _do_not_send
    else:  # fail fast on missing Telegram settings, before calling the price API
        target = config.telegram.resolve(env)
        send = TelegramNotifier(require_env(BOT_TOKEN_ENV, env), target, http).send

    db_path = args.db or Path(env.get(DB_ENV) or DEFAULT_DB)
    with PriceHistory(db_path) as history:
        report = run_instance(
            config,
            client,
            history,
            send,
            now=now,
            timezone=TIMEZONE,
            dry_run=args.dry_run,
            http=http,
        )

    if args.dry_run:
        separator = "\n" + "-" * 60 + "\n"
        print(separator.join(report.messages) if report.messages else "(no messages)")
        print(separator.rstrip())
    mode = "DRY RUN — nothing sent or stored" if args.dry_run else f"history: {db_path}"
    print(
        f"{'warm-up · ' if report.warmup else ''}{report.fetched} fetched · "
        f"{report.candidates} candidates · {report.deals} deals · "
        f"{report.alerts_sent} alerts · {report.in_summary} in summary · "
        f"{report.skipped_repeats} repeats skipped · {mode}"
    )
    return 0


def _do_not_send(text: str) -> None:
    raise AssertionError("dry run must not send messages")  # pragma: no cover


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
