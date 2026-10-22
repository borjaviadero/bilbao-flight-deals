# Architecture

## Concepts

| Concept | What it is | Example |
|---|---|---|
| **Watcher** | A component that looks for deals in one category. One Docker image per watcher. | `flights`, later `clothes`, `watches` |
| **Instance** | The same watcher running with its own settings. One config file each. | `flights-bio`, later `flights-mad`, `flights-bcn` |
| **Core** | Shared logic used by every watcher. | Price history, deal rules, de-duplication, Telegram |

Adding a new **instance** means adding a YAML file — no new code.
Adding a new **watcher** means adding a new folder under `watchers/` that implements the same small interface.

## Flow

```mermaid
sequenceDiagram
    participant K as Kubernetes CronJob
    participant W as Watcher (flights-bio)
    participant API as Price API
    participant DB as PostgreSQL
    participant TG as Telegram

    K->>W: run every few hours
    W->>API: fetch round-trip fares from BIO
    API-->>W: fares
    W->>W: apply filters (dates, stops)
    W->>DB: store prices
    W->>DB: get usual price per route
    W->>W: is it a deal? (-30% or < €60 pp)
    alt new deal (or lower than last alert)
        W->>TG: send alert to topic
        W->>DB: remember alert
    end
```

## Telegram layout

Telegram groups can have **topics**, but topics cannot be nested. Three levels are mapped like this:

| Level | Telegram | Example |
|---|---|---|
| Whole system | Chat folder | "Deals" |
| Watcher | Group (supergroup with topics) | "Flights" |
| Instance | Topic inside the group | "Bilbao" |

Display names are free text. One bot serves every group. Each instance config names the environment variables that hold its group and topic IDs (`chat_id_env`, `topic_id_env`), so no IDs live in the repository. Setup steps: [telegram-setup.md](telegram-setup.md).

## Where it runs

```mermaid
flowchart LR
    GH["GitHub<br/>code + Actions"] -->|build & push image| GHCR["GitHub Container Registry"]
    TF["Terraform"] -->|creates| VM["Oracle Cloud VM<br/>Always Free (ARM)"]
    VM --> K3S["k3s cluster"]
    GHCR -->|pull image| K3S
    K3S --> TGAPI["Telegram"]
```

## Design notes

- **Free by design.** Oracle Cloud Always Free ARM (2 OCPU / 12 GB), Travelpayouts free data API, GitHub free tier.
- **ARM images.** The server is ARM, so images are built for `linux/arm64` (and `amd64` for local use).
- **Prices are cached, not live.** The free price API returns recently searched fares. Good for spotting drops; the price may change when opening the link.
- **Cold start.** "Usual price" needs history, so for the first weeks the `< €60 pp` rule does most of the work.
