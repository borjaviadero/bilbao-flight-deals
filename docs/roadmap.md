# Roadmap

## Version 1 — flights from Bilbao

| Phase | Goal | Done when |
|---|---|---|
| 0. Setup | Tools installed (WSL), Oracle Cloud account, Telegram bot, repo structure | This structure is merged |
| 1. Local watcher | Flights watcher runs locally | First test alert arrives on Telegram |
| 2. Docker | Watcher packaged as an image | Image published to GHCR by GitHub Actions |
| 3. Terraform | Free Oracle Cloud VM created from code | `terraform apply` creates network + VM |
| 4. Kubernetes | System running 24/7 on k3s | Alerts arrive without any laptop on |
| 5. Automation & ops | CI/CD, backups, monitoring | A merge to `main` deploys itself; alerts if something breaks |

## Future

| Version | Adds |
|---|---|
| 2 | More departure airports (Madrid, Barcelona…) — new config files, same watcher |
| 3 | Clothes watcher, with instances per shop or size |
| 4 | Watches watcher, or other categories |
| Extras | Bot commands (`/price`, `/pause`), sharing groups with family or friends |
