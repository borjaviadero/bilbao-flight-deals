# flights watcher — `flights-watcher`

Looks for round-trip flight deals for one instance config (for example [`flights-bio.yaml`](../../config/watchers/flights-bio.yaml)) and reports them through `dealhunter-core`.

| Module | Status | What it does |
|---|---|---|
| `config.py` | ✅ | Adds the flights `search` section (origin, destinations, passengers, currency, max stops) to the shared instance config. |
| `models.py` | ✅ | `Fare` (normalised round-trip fare: price per person, stops per leg, nights, absolute booking link) and `Candidate` (a fare plus its deal window). |
| `price_api.py` | ✅ | Client for `GET /aviasales/v3/prices_for_dates`. Token in the `X-Access-Token` header; malformed entries are skipped with a warning. |
| `search.py` | ✅ | `fetch_fares`: one request per departure month covered by the deal windows. `select_candidates`: max stops on either leg, deal window by days ahead, de-duplication (cheapest per route, dates and carrier), sorted by price. |
| `cli.py` | ✅ | `python -m flights_watcher search --config …` lists the candidates. Read-only: stores nothing, sends nothing. |
| Price history and deal rules | Phase 1 | Next pull request. |
| Telegram alerts | Phase 1 | `run` command with dry-run mode. |
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
make search                          # flights-bio, needs .env with TRAVELPAYOUTS_API_TOKEN
make search INSTANCE=flights-mad     # another instance
uv run python -m flights_watcher --help
```
