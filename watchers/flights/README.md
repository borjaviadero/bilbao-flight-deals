# flights watcher — `flights-watcher`

Looks for round-trip flight deals for one instance config (for example [`flights-bio.yaml`](../../config/watchers/flights-bio.yaml)) and reports them through `dealhunter-core`.

| Module | Status | What it does |
|---|---|---|
| `config.py` | ✅ | Adds the flights `search` section (origin, destinations, passengers, currency, max stops) to the shared instance config. |
| Price API client | Phase 1 | Fetches fares from the Travelpayouts / Aviasales Data API. |
| Filters | Phase 1 | Applies max stops and the departure range of the deal windows. |
| CLI | Phase 1 | Runs one search for an instance. |
| `Dockerfile` | Phase 2 | Container image. |

## Layout

```
watchers/flights/
├── pyproject.toml           # depends on dealhunter-core
├── src/flights_watcher/     # source code
└── tests/                   # unit tests, including validation of every config/watchers/flights-*.yaml
```
