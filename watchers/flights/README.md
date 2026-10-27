# flights watcher — `flights-watcher`

Looks for round-trip flight deals for one instance config (for example [`flights-bio.yaml`](../../config/watchers/flights-bio.yaml)) and reports them through `dealhunter-core`.

| Module | Status | What it does |
|---|---|---|
| `config.py` | ✅ | Adds the flights `search` section (origin, destinations, passengers, currency, max stops, `trip_length`) to the shared instance config. `trip_length` sets the nights allowed by outbound flight time (short flights → short trips); `city_names` overrides downloaded names (e.g. `BIO: Bilbao`). |
| `models.py` | ✅ | `Fare` (normalised round-trip fare: price per person, stops per leg, flight time per leg, nights, absolute booking link) and `Candidate` (a fare plus its deal window). |
| `price_api.py` | ✅ | Client for `GET /aviasales/v3/prices_for_dates`. Token in the `X-Access-Token` header; malformed entries are skipped with a warning. |
| `search.py` | ✅ | `fetch_fares`: one request per departure month covered by the deal windows. `select_candidates`: max stops on either leg, trip length for the flight time, deal window by days ahead, de-duplication (cheapest per route, dates and carrier), sorted by price. |
| `deals.py` | ✅ | Flights keys for the history (`route_key` = origin-destination airports), observations from candidates, and `find_opportunities` (evaluates each candidate against its window, using the route's usual price). |
| `messages.py` | ✅ | Telegram texts in English and Spanish (HTML, escaped): deal alert (departure time, flight time and stops per leg; a note that the price is indicative), summary of the rest, warm-up start message. Destinations shown as `Milán (MXP)`, falling back to codes. |
| `places.py` | ✅ | City and airline names for the messages, from the Travelpayouts `cities.json` and `airlines.json` data files (no token). Each cached 30 days in the history `cache` table; on failure the messages use codes. |
| `runner.py` | ✅ | One complete run: search → warm-up or evaluate and plan → record prices → send (each alert logged once delivered) → finish. `dry_run` writes and sends nothing. |
| `cli.py` | ✅ | `search` (read-only table) and `run [--dry-run] [--db PATH]`. |
| `Dockerfile` | Phase 2 | Container image. |

## Layout

```
watchers/flights/
├── pyproject.toml           # depends on dealhunter-core
├── src/flights_watcher/     # source code
└── tests/                   # unit tests; fixtures/ holds a sample API response
```

## Usage

```bash
make search                          # table of candidates (read-only)
make dry-run                         # full run, prints the Telegram messages, stores nothing
make run                             # full run: records history and sends messages
make search INSTANCE=flights-mad     # another instance
uv run python -m flights_watcher --help
```
