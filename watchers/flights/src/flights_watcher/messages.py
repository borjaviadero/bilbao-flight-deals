"""Telegram message texts for the flights watcher, in English and Spanish.

Messages use Telegram's HTML mode, so every dynamic value is escaped.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from html import escape

from dealhunter_core.alerts import Opportunity
from dealhunter_core.config import Language
from dealhunter_core.rules import fmt
from flights_watcher.config import FlightsInstanceConfig
from flights_watcher.models import Candidate, Fare

WEEKDAYS = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "es": ("lun", "mar", "mié", "jue", "vie", "sáb", "dom"),
}
MONTHS = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
}

TEXTS: dict[Language, dict[str, str]] = {
    "en": {
        "nights": "{n} nights",
        "night": "1 night",
        "outbound": "Out",
        "return": "Back",
        "direct": "direct",
        "stop": "1 stop",
        "stops": "{n} stops",
        "airline": "airline {name}",
        "per_person": "{price} € per person · {total} € for {n}",
        "drop": "{drop}% below usual ({usual} €)",
        "departs_in": "Departs in {days} days",
        "view": "View flight",
        "indicative": "🔎 Indicative price from recent searches: check it before buying.",
        "summary_title": "📋 {n} more deals (beyond the {max} alerts)",
        "summary_title_one": "📋 1 more deal (beyond the {max} alerts)",
        "per_person_short": "{price} € pp",
        "with_stops": "with stops",
        "start_title": "👋 Now watching flights from {origin}",
        "start_scope": "Every run checks {days_min} to {days_max} days ahead, max {stops} stop(s).",
        "start_recorded": "First run: {n} prices recorded. Alerts start from the next run.",
        "start_top": "Cheapest right now:",
        "start_none": "No fares pass the filters right now.",
    },
    "es": {
        "nights": "{n} noches",
        "night": "1 noche",
        "outbound": "Ida",
        "return": "Vuelta",
        "direct": "directo",
        "stop": "1 escala",
        "stops": "{n} escalas",
        "airline": "aerolínea {name}",
        "per_person": "{price} € por persona · {total} € para {n}",
        "drop": "{drop}% por debajo de lo habitual ({usual} €)",
        "departs_in": "Sale dentro de {days} días",
        "view": "Ver vuelo",
        "indicative": (
            "🔎 Precio orientativo de búsquedas recientes: compruébalo antes de comprar."
        ),
        "summary_title": "📋 {n} chollos más (no cabían en los {max} avisos)",
        "summary_title_one": "📋 1 chollo más (no cabía en los {max} avisos)",
        "per_person_short": "{price} €/pers.",
        "with_stops": "con escalas",
        "start_title": "👋 Empiezo a vigilar vuelos desde {origin}",
        "start_scope": (
            "Cada búsqueda mira de {days_min} a {days_max} días vista, máx. {stops} escala(s)."
        ),
        "start_recorded": (
            "Primera ejecución: {n} precios guardados. Los avisos empiezan en la siguiente."
        ),
        "start_top": "Lo más barato ahora mismo:",
        "start_none": "Ahora mismo ningún vuelo pasa los filtros.",
    },
}


def short_date(moment: datetime, language: Language) -> str:
    """``Thu 12 Dec`` / ``jue 12 dic``."""
    weekday = WEEKDAYS[language][moment.weekday()]
    month = MONTHS[language][moment.month - 1]
    return f"{weekday} {moment.day} {month}"


def clock(moment: datetime) -> str:
    """``07:05``, in the local time of the airport (as given by the price source)."""
    return f"{moment.hour:02d}:{moment.minute:02d}"


def flight_time(minutes: int) -> str:
    """``2 h 05 min`` / ``2 h`` / ``45 min``."""
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h {rest:02d} min" if rest else f"{hours} h"


def leg(name: str, moment: datetime, minutes: int, stops: int, language: Language) -> str:
    """``Ida: jue 10 dic, 08:00 · 2 h · directo``."""
    t = TEXTS[language]
    stops_text = (
        t["direct"] if stops == 0 else t["stop"] if stops == 1 else t["stops"].format(n=stops)
    )
    parts = [f"{name}: {short_date(moment, language)}, {clock(moment)}"]
    if minutes > 0:
        parts.append(flight_time(minutes))
    parts.append(stops_text)
    return " · ".join(parts)


CityNames = Mapping[str, str]  # IATA city code → name in the message language
AirlineNames = Mapping[str, str]  # IATA airline code → name


def destination(fare: Fare, names: CityNames) -> str:
    """``Milán (MXP)``; without a known name, ``MXP (MIL)``."""
    name = names.get(fare.destination_city) or names.get(fare.destination_airport)
    if name:
        return f"{name} ({fare.destination_airport})"
    if fare.destination_city and fare.destination_city != fare.destination_airport:
        return f"{fare.destination_airport} ({fare.destination_city})"
    return fare.destination_airport


def route(fare: Fare, names: CityNames) -> str:
    """``Bilbao → Milán (MXP)``."""
    origin = names.get(fare.origin_airport, fare.origin_airport)
    return f"{origin} → {destination(fare, names)}"


def alert_message(
    opportunity: Opportunity[Candidate],
    config: FlightsInstanceConfig,
    language: Language,
    names: CityNames | None = None,
    airlines: AirlineNames | None = None,
) -> str:
    """One deal, as a Telegram HTML message."""
    t = TEXTS[language]
    candidate = opportunity.item
    fare = candidate.fare
    passengers = config.search.passengers
    label = config.window_named(opportunity.window).label_for(language)

    nights = t["night"] if fare.nights == 1 else t["nights"].format(n=fare.nights)
    lines = [
        f"<b>{escape(label)} · {escape(route(fare, names or {}))}</b>",
        "🛫 "
        + leg(t["outbound"], fare.departure_at, fare.outbound_minutes, fare.stops_out, language),
        "🛬 " + leg(t["return"], fare.return_at, fare.return_minutes, fare.stops_back, language),
        f"🌙 {nights} · "
        + t["airline"].format(name=escape((airlines or {}).get(fare.airline, fare.airline))),
        "💶 "
        + t["per_person"].format(
            price=fmt(fare.price_per_person), total=fmt(fare.total_price(passengers)), n=passengers
        ),
    ]
    evaluation = opportunity.evaluation
    if evaluation.drop_percent is not None and evaluation.drop_percent > 0:
        lines.append(
            "📉 "
            + t["drop"].format(
                drop=f"{evaluation.drop_percent:.0f}", usual=fmt(evaluation.usual_price)
            )
        )
    lines.append("⏳ " + t["departs_in"].format(days=candidate.days_ahead))
    lines.append(t["indicative"])
    lines.append(f'<a href="{escape(fare.link, quote=True)}">{t["view"]}</a>')
    return "\n".join(lines)


def date_range(start: datetime, end: datetime, language: Language) -> str:
    """``1-8 mar`` within a month, ``27 feb - 6 mar`` across months."""
    months = MONTHS[language]
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}-{end.day} {months[end.month - 1]}"
    return f"{start.day} {months[start.month - 1]} - {end.day} {months[end.month - 1]}"


def summary_line(
    candidate: Candidate,
    language: Language,
    names: CityNames,
    drop: Decimal | None = None,
) -> str:
    """Compact one-line version of a deal, with a link.

    ``• Lisboa (LIS) · 1-8 mar · 7 noches · 80 €/pers. · -33% · directo``
    """
    t = TEXTS[language]
    fare = candidate.fare
    nights = t["night"] if fare.nights == 1 else t["nights"].format(n=fare.nights)
    parts = [
        escape(destination(fare, names)),
        date_range(fare.departure_at, fare.return_at, language),
        nights,
        t["per_person_short"].format(price=fmt(fare.price_per_person)),
    ]
    if drop is not None and drop > 0:
        parts.append(f"-{drop:.0f}%")
    parts.append(t["direct"] if fare.max_stops == 0 else t["with_stops"])
    return f'• <a href="{escape(fare.link, quote=True)}">{" · ".join(parts)}</a>'


def summary_message(
    opportunities: Sequence[Opportunity[Candidate]],
    language: Language,
    names: CityNames | None = None,
    *,
    max_alerts: int,
) -> str:
    """The deals that did not fit in the per-run cap of ``max_alerts``, in one message."""
    t = TEXTS[language]
    count = len(opportunities)
    title = (
        t["summary_title_one"].format(max=max_alerts)
        if count == 1
        else t["summary_title"].format(n=count, max=max_alerts)
    )
    lines = [f"<b>{title}</b>"]
    lines += [
        summary_line(o.item, language, names or {}, o.evaluation.drop_percent)
        for o in opportunities
    ]
    return _truncate("\n".join(lines))


def start_message(
    config: FlightsInstanceConfig,
    candidates: Sequence[Candidate],
    recorded: int,
    language: Language,
    names: CityNames | None = None,
    *,
    top: int = 5,
) -> str:
    """Warm-up run: say what is being watched and show the cheapest fares."""
    t = TEXTS[language]
    known = names or {}
    origin = known.get(config.search.origin, config.search.origin)
    lines = [
        f"<b>{t['start_title'].format(origin=escape(origin))}</b>",
        t["start_scope"].format(
            days_min=config.min_days_ahead,
            days_max=config.max_days_ahead,
            stops=config.search.max_stops,
        ),
        t["start_recorded"].format(n=recorded),
        "",
    ]
    if candidates:
        lines.append(t["start_top"])
        lines += [summary_line(c, language, known) for c in candidates[:top]]
    else:
        lines.append(t["start_none"])
    return _truncate("\n".join(lines))


def _truncate(text: str, limit: int = 4000) -> str:
    """Keep messages under Telegram's limit by dropping whole lines from the end."""
    if len(text) <= limit:
        return text
    lines = text.split("\n")
    while lines and len("\n".join([*lines, "…"])) > limit:
        lines.pop()
    return "\n".join([*lines, "…"])
