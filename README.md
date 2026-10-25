# bilbao-flight-deals

A self-hosted deal hunter that watches flight prices departing from **Bilbao (BIO)** and sends an alert to **Telegram** when a fare is clearly cheaper than usual.

It runs 24/7 on a free cloud server, provisioned with **Terraform** and orchestrated with **Kubernetes (k3s)**, with every component packaged as a **Docker** image.

> **Status:** 🚧 Phase 0 — setup in progress: repository ✅ · dev tools ✅ · Telegram bot ✅ · price API ✅ · cloud account ⏳. See the [roadmap](docs/roadmap.md).

---

## What it does

1. **Watches** round-trip fares from Bilbao to any destination, several times a day.
2. **Filters** them: direct or 1-stop flights, departing between 7 days and 6 months ahead.
3. **Remembers** every price it sees, so it learns what "normal" looks like for each route.
4. **Decides** whether a fare is a deal, with stricter rules for short notice:

   | Departure | Alert if | Label |
   |---|---|---|
   | 30 days – 6 months | ≥ 30% below usual **or** < €60 per person | ✈️ Deal |
   | 7 – 29 days | ≥ 50% below usual **or** ≤ €30 per person | ⚡ Super deal · last minute |
5. **Alerts** on Telegram with the price, the drop and a link — without repeating itself unless the price drops further.
6. **Summarises** the best fares every Sunday.

Example alert:

```
✈️ Deal: Bilbao → Rome
Out 14 Dec · back 18 Dec (4 nights) · direct
€98 for 2 people (€49 pp)
Usually ~€170 → -42%
[View flight]
```

## Architecture

The system is split into **watchers** (one per category, e.g. flights, clothes, watches) that share a common **core**. Each watcher can run several **instances** with different settings — for example *flights from Bilbao*, *flights from Madrid* — all from the same image, each defined by a config file.

```mermaid
flowchart TD
    subgraph Watchers
        F["✈️ flights watcher<br/>instance: BIO"]
        C["👕 clothes watcher<br/>(future)"]
        W["⌚ watches watcher<br/>(future)"]
    end
    F --> CORE
    C -.-> CORE
    W -.-> CORE
    CORE["Core<br/>price history · deal rules · de-duplication"] --> DB[("PostgreSQL")]
    CORE --> TG["Telegram bot<br/>group per category · topic per instance"]
```

More detail in [docs/architecture.md](docs/architecture.md).

## Tech stack

| Area | Tool |
|---|---|
| Language | Python |
| Containers | Docker, GitHub Container Registry |
| Orchestration | Kubernetes (k3s) |
| Infrastructure as Code | Terraform (Oracle Cloud Always Free) |
| CI/CD | GitHub Actions |
| Data | PostgreSQL |
| Flight prices | Travelpayouts / Aviasales Data API |
| Notifications | Telegram Bot API |

Everything runs on free tiers.

## Getting started

1. Install the tools: [docs/development-setup.md](docs/development-setup.md)
2. Set up Telegram: [docs/telegram-setup.md](docs/telegram-setup.md)
3. Get a price API token: [docs/price-source.md](docs/price-source.md)
4. Copy `.env.example` to `.env` and fill in the values

The watchers themselves arrive in Phase 1.

## Repository layout

```
.
├── config/watchers/   # One YAML file per watcher instance (e.g. flights-bio.yaml)
├── core/              # Shared code: price history, deal rules, Telegram notifier
├── watchers/flights/  # Flights watcher (fetches fares from the price API)
├── infra/terraform/   # Cloud infrastructure (network, VM)
├── infra/k8s/         # Kubernetes manifests
├── docs/              # Architecture, roadmap, setup guides and price source notes
└── .github/           # Pull request template (CI workflows later)
```

Root files: `.env.example` (required environment variables), `.gitignore` (files never tracked), `.gitattributes` (LF line endings), `.editorconfig` (shared formatting), `CONTRIBUTING.md` (workflow and conventions), `LICENSE`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch, commit and pull request conventions.

## License

[MIT](LICENSE)
