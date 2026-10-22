# k8s

Kubernetes manifests for the k3s cluster. Planned for **Phase 4**.

- One `CronJob` per watcher instance (generated from `config/watchers/`)
- PostgreSQL for price history
- `Secret`s for API tokens (never committed)
