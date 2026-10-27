"""City names for messages (``MIL`` → ``Milán``).

Names come from the public Travelpayouts data file ``/data/<lang>/cities.json`` (no
token needed). The list changes rarely, so it is cached in the history database and
refreshed every 30 days. If it cannot be fetched, messages fall back to IATA codes.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from dealhunter_core.config import Language
from dealhunter_core.history import PriceHistory
from dealhunter_core.http import HttpError, JsonHttpClient

logger = logging.getLogger(__name__)

CITIES_URL = "https://api.travelpayouts.com/data/{language}/cities.json"
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


def city_names(
    http: JsonHttpClient,
    history: PriceHistory,
    language: Language,
    now: datetime,
    *,
    store: bool = True,
) -> dict[str, str]:
    """City code → name in ``language``, from the cache or freshly downloaded.

    Never raises: on failure it logs a warning and returns whatever it has (possibly
    an empty mapping). With ``store=False`` (dry runs) the cache is read but not written.
    """
    cache_name = f"cities:{language}"
    cached = history.cached(cache_name, max_age=MAX_AGE, now=now)
    if isinstance(cached, dict) and cached:
        return {str(k): str(v) for k, v in cached.items()}

    try:
        names = parse_cities(http.get_json(CITIES_URL.format(language=language)))
    except HttpError as exc:
        logger.warning("city names unavailable, using airport codes: %s", exc)
        return {}

    if names and store:
        history.store_cache(cache_name, names, now)
    logger.info("loaded %d city names (%s)", len(names), language)
    return names
