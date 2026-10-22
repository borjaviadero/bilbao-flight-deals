# core

Shared code used by every watcher. Planned for **Phase 1**.

- **Price history** — stores every fare/price seen and computes the usual price per item or route.
- **Deal rules** — evaluates the `deal_rules` section of an instance config.
- **De-duplication** — remembers what was already alerted.
- **Notifier** — sends messages to the right Telegram group and topic.
