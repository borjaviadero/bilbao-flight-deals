"""Readable names for messages: cities (``MIL`` → ``Milán``) and airlines (``V7`` → ``Volotea``).

Names come from public Travelpayouts data files (no token needed):

- ``/data/<lang>/cities.json``, in the message language;
- ``/data/en/airlines.json``, in English (airline names are brand names).

The lists change rarely, so each one is cached in the history database and refreshed
every 30 days. If a list cannot be fetched, messages fall back to IATA codes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

from dealhunter_core.config import Language
from dealhunter_core.history import PriceHistory
from dealhunter_core.http import HttpError, JsonHttpClient

logger = logging.getLogger(__name__)

CITIES_URL = "https://api.travelpayouts.com/data/{language}/cities.json"
AIRLINES_URL = "https://api.travelpayouts.com/data/en/airlines.json"
MAX_AGE = timedelta(days=30)


def parse_cities(payload: Any) -> dict[str, str]:
    """``[{"code": "MIL", "name": "Milán", ...}, ...]`` → ``{"MIL": "Milán"}``."""
    if not isinstance(payload, list):
        return {}
    return {
        str(item["code"]): str(item["name"])
        for item in payload
        if isinstance(item, Mapping) and item.get("code") and item.get("name")
    }


def parse_airlines(payload: Any) -> dict[str, str]:
    """``[{"code": "V7", "name": "Volotea", ...}, ...]`` → ``{"V7": "Volotea"}``.

    Entries without ``name`` use ``name_translations.en`` when present.
    """
    if not isinstance(payload, list):
        return {}
    names: dict[str, str] = {}
    for item in payload:
        if not isinstance(item, Mapping) or not item.get("code"):
            continue
        translations = item.get("name_translations")
        english = translations.get("en") if isinstance(translations, Mapping) else None
        name = item.get("name") or english
        if name:
            names[str(item["code"])] = str(name)
    return names


def city_names(
    http: JsonHttpClient,
    history: PriceHistory,
    language: Language,
    now: datetime,
    *,
    store: bool = True,
) -> dict[str, str]:
    """City code → name in ``language``. See :func:`_reference_names`."""
    return _reference_names(
        http,
        history,
        url=CITIES_URL.format(language=language),
        cache_name=f"cities:{language}",
        parse=parse_cities,
        what=f"city names ({language})",
        now=now,
        store=store,
    )


def airline_names(
    http: JsonHttpClient, history: PriceHistory, now: datetime, *, store: bool = True
) -> dict[str, str]:
    """Airline IATA code → name. See :func:`_reference_names`."""
    return _reference_names(
        http,
        history,
        url=AIRLINES_URL,
        cache_name="airlines:en",
        parse=parse_airlines,
        what="airline names",
        now=now,
        store=store,
    )


def _reference_names(
    http: JsonHttpClient,
    history: PriceHistory,
    *,
    url: str,
    cache_name: str,
    parse: Callable[[Any], dict[str, str]],
    what: str,
    now: datetime,
    store: bool,
) -> dict[str, str]:
    """Code → name, from the cache or freshly downloaded.

    Never raises: on failure it logs a warning and returns an empty mapping, so
    messages use codes. With ``store=False`` (dry runs) the cache is read but not written.
    """
    cached = history.cached(cache_name, max_age=MAX_AGE, now=now)
    if isinstance(cached, dict) and cached:
        return {str(k): str(v) for k, v in cached.items()}

    try:
        names = parse(http.get_json(url))
    except HttpError as exc:
        logger.warning("%s unavailable, using codes: %s", what, exc)
        return {}

    if names and store:
        history.store_cache(cache_name, names, now)
    logger.info("loaded %d %s", len(names), what)
    return names
