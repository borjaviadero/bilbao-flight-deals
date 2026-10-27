"""Telegram message texts for the flights watcher, in English and Spanish.

Messages use Telegram's HTML mode, so every dynamic value is escaped.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
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
        "direct": "Direct both ways",
        "stops": "Stops: {out} out · {back} back",
        "per_person": "{price} € per person · {total} € for {n}",
        "drop": "{drop}% below usual ({usual} €)",
        "departs_in": "Departs in {days} days",
        "view": "View flight",
        "summary_title": "📋 {n} more deals this run",
        "summary_title_one": "📋 1 more deal this run",
        "start_title": "👋 Now watching flights from {origin}",
        "start_scope": "Every run checks {days_min} to {days_max} days ahead, max {stops} stop(s).",
        "start_recorded": "First run: {n} prices recorded. Alerts start from the next run.",
        "start_top": "Cheapest right now:",
        "start_none": "No fares pass the filters right now.",
    },
    "es": {
        "nights": "{n} noches",
        "night": "1 noche",
        "direct": "Directo ida y vuelta",
        "stops": "Escalas: {out} ida · {back} vuelta",
        "per_person": "{price} € por persona · {total} € para {n}",
        "drop": "{drop}% por debajo de lo habitual ({usual} €)",
        "departs_in": "Sale dentro de {days} días",
        "view": "Ver vuelo",
        "summary_title": "📋 {n} chollos más en esta búsqueda",
        "summary_title_one": "📋 1 chollo más en esta búsqueda",
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


def route(fare: Fare) -> str:
    """``BIO → MXP (MIL)``; the city code is shown when it differs from the airport."""
    destination = fare.destination_airport
    if fare.destination_city and fare.destination_city != destination:
        destination += f" ({fare.destination_city})"
    return f"{fare.origin_airport} → {destination}"


def alert_message(
    opportunity: Opportunity[Candidate], config: FlightsInstanceConfig, language: Language
) -> str:
    """One deal, as a Telegram HTML message."""
    t = TEXTS[language]
    candidate = opportunity.item
    fare = candidate.fare
    passengers = config.search.passengers
    label = config.window_named(opportunity.window).label_for(language)

    nights = t["night"] if fare.nights == 1 else t["nights"].format(n=fare.nights)
    stops = (
        t["direct"]
        if fare.max_stops == 0
        else t["stops"].format(out=fare.stops_out, back=fare.stops_back)
    )
    lines = [
        f"<b>{escape(label)} · {escape(route(fare))}</b>",
        f"📅 {short_date(fare.departure_at, language)} → "
        f"{short_date(fare.return_at, language)} · {nights}",
        f"🛫 {escape(stops)} · {escape(fare.airline)}",
        "💶 "
        + t["per_person"].format(
            price=fmt(fare.price_per_person), total=fmt(fare.total_price(passengers)), n=passengers
        ),
    ]
    evaluation = opportunity.evaluation
    if evaluation.drop_percent is not None and evaluation.drop_percent > 0:
        lines.append(
            "📉 "
            + t["drop"].format(drop=fmt(evaluation.drop_percent), usual=fmt(evaluation.usual_price))
        )
    lines.append("⏳ " + t["departs_in"].format(days=candidate.days_ahead))
    lines.append(f'<a href="{escape(fare.link, quote=True)}">{t["view"]}</a>')
    return "\n".join(lines)


def summary_line(candidate: Candidate, language: Language) -> str:
    """Compact one-line version of a deal, with a link."""
    fare = candidate.fare
    text = (
        f"{escape(fare.destination_airport)} · {short_date(fare.departure_at, language)} → "
        f"{short_date(fare.return_at, language)} · {fmt(fare.price_per_person)} €"
    )
    return f'• <a href="{escape(fare.link, quote=True)}">{text}</a>'


def summary_message(opportunities: Sequence[Opportunity[Candidate]], language: Language) -> str:
    """The deals that did not fit in the per-run cap, in one message."""
    t = TEXTS[language]
    count = len(opportunities)
    title = t["summary_title_one"] if count == 1 else t["summary_title"].format(n=count)
    lines = [f"<b>{title}</b>"]
    lines += [summary_line(o.item, language) for o in opportunities]
    return _truncate("\n".join(lines))


def start_message(
    config: FlightsInstanceConfig,
    candidates: Sequence[Candidate],
    recorded: int,
    language: Language,
    *,
    top: int = 5,
) -> str:
    """Warm-up run: say what is being watched and show the cheapest fares."""
    t = TEXTS[language]
    lines = [
        f"<b>{t['start_title'].format(origin=escape(config.search.origin))}</b>",
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
        lines += [summary_line(c, language) for c in candidates[:top]]
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
