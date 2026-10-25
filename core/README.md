# core

Shared code used by every watcher. Planned for **Phase 1**.

- **Price history** — stores every fare/price seen and computes the usual price per item or route.
- **Deal rules** — evaluates the `deal_windows` of an instance config (departure date ranges, each with its own rules).
- **De-duplication** — remembers what was already alerted.
- **Notifier** — sends messages to the right Telegram group and topic.
