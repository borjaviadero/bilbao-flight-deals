# core — `dealhunter-core`

Shared Python package used by every watcher.

| Module | Status | What it does |
|---|---|---|
| `config.py` | ✅ | Loads and validates instance YAML files: schedule, `deal_windows`, alerts and Telegram target. Unknown keys are rejected. Telegram IDs are read from the environment variables named in the config. |
| `http.py` | ✅ | JSON-over-HTTPS client on the standard library: timeout, retries with exponential backoff for 429/5xx and network errors (honours `Retry-After`, capped at 60 s), errors that never include headers or query strings. Injectable transport for tests. |
| Price history | Phase 1 | Stores every fare/price seen and computes the usual price per item or route (SQLite). |
| Deal rules | Phase 1 | Evaluates the `deal_windows` of an instance config (departure date ranges, each with its own rules). |
| De-duplication | Phase 1 | Remembers what was already alerted. |
| Notifier | Phase 1 | Sends messages to the right Telegram group and topic. |

## Layout

```
core/
├── pyproject.toml           # package metadata and dependencies
├── src/dealhunter_core/     # source code
└── tests/                   # unit tests (pytest)
```

Run the checks from the repository root with `make check`.
