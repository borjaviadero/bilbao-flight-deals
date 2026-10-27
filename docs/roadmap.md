# Roadmap

## Version 1 — flights from Bilbao

| Phase | Goal | Done when | Status |
|---|---|---|---|
| 0. Setup | Repo conventions, local tools, Telegram bot, cloud and API accounts | Every item in the checklist below is ticked | ✅ Done |
| 1. Local watcher | Flights watcher runs locally | First real deal alert arrives on Telegram | ✅ Done |
| 2. Docker | Watcher packaged as an image | Image published to GHCR by GitHub Actions | 🚧 Next |
| 3. Terraform | Free Oracle Cloud VM created from code | `terraform apply` creates network + VM | ⏳ |
| 4. Kubernetes | System running 24/7 on k3s | Alerts arrive without any laptop on | ⏳ |
| 5. Automation & ops | CI/CD, backups, monitoring | A merge to `main` deploys itself; alerts if something breaks | ⏳ |

### Phase 0 checklist

- [x] Repository structure and documentation
- [x] Repository conventions (`.gitattributes`, `.editorconfig`, PR template, `CONTRIBUTING.md`)
- [x] Local tools installed — see [development-setup.md](development-setup.md)
- [x] Telegram bot, group and topic — see [telegram-setup.md](telegram-setup.md)
- [x] Travelpayouts account and API token — see [price-source.md](price-source.md)
- [x] Oracle Cloud Always Free account — see [oracle-cloud-setup.md](oracle-cloud-setup.md)

### Phase 3 checklist

- [ ] OCI API key and SSH key in WSL — see [oracle-cloud-setup.md](oracle-cloud-setup.md)
- [ ] Bootstrap stack: compartment, state bucket, budget alert
- [ ] Main stack: network and ARM VM (2 OCPU / 12 GB), state in the bucket
- [ ] SSH into the VM

### Phase 2 checklist

- [ ] Dockerfile for the flights watcher and `make docker-*` targets; same results as `make run`
- [ ] GitHub Actions: `make check` on every pull request
- [ ] GitHub Actions: image built for `amd64` and `arm64` and pushed to GHCR on every merge to `main`

### Phase 1 checklist

- [x] Python workspace (uv), quality tooling (Ruff, mypy, pytest) and validated instance config
- [x] Price API client and filters (`make search`)
- [x] Price history (SQLite) and deal rules
- [x] Telegram notifier and `run` command (with dry-run)
- [x] First real deal alert on Telegram (27 Oct 2026: 5 alerts in the Bilbao topic)

Until Phase 4 the watcher runs only when started by hand (`make run`); the `schedule` in each instance config is used by the Kubernetes CronJob. The weekly summary (`alerts.weekly_summary`) is planned for Phase 5.

## Future

| Version | Adds |
|---|---|
| 2 | More departure airports (Madrid, Barcelona…) — new config files, same watcher |
| 3 | Clothes watcher, with instances per shop or size |
| 4 | Watches watcher, or other categories |
| Extras | Bot commands (`/price`, `/pause`), sharing groups with family or friends |
