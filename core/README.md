# core — `dealhunter-core`

Shared Python package used by every watcher.

| Module | Status | What it does |
|---|---|---|
| `config.py` | ✅ | Loads and validates instance YAML files: schedule, `deal_windows` (labels per language), alerts and Telegram target (including message `language`: `en` or `es`). Unknown keys are rejected. Telegram IDs are read from the environment variables named in the config. |
| `http.py` | ✅ | JSON-over-HTTPS client on the standard library: timeout, retries with exponential backoff for 429/5xx and network errors (honours `Retry-After`, capped at 60 s), errors that never include headers or query strings. Injectable transport for tests. |
| `history.py` | ✅ | SQLite store: `runs` (to detect the warm-up run), `observations` (every price seen) `alerts` (last alert per item) and `cache` (reference data such as city names, with its download time). `usual_price` = **median** of a route's prices in the look-back period, or `None` below `min_observations`. Prices kept as text for `Decimal` precision; timestamps UTC. |
| `rules.py` | ✅ | `evaluate(window, price, usual)`: applies `drop_vs_usual` and `max_price_per_person` with the window's `match` (`any`/`all`) and explains which rules matched. |
| `alerts.py` | ✅ | `plan_alerts`: skips items already alerted at the same or a lower price, ranks the rest (biggest drop, then lowest price) and caps individual alerts per run; the rest go to a summary. |
| `telegram.py` | ✅ | `TelegramNotifier`: posts HTML messages to a group topic via the Bot API (link previews off, 4096-char limit). The bot token is part of the URL, so errors are re-raised with it redacted. |

## Layout

```
core/
├── pyproject.toml           # package metadata and dependencies
├── src/dealhunter_core/     # source code
└── tests/                   # unit tests (pytest)
```

Run the checks from the repository root with `make check`.
