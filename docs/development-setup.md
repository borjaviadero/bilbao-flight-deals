# Development setup

Tools needed to work on this project locally. The reference environment is **WSL 2 on Windows** with Ubuntu; any recent Debian/Ubuntu works the same way.

## Prerequisites

| Tool | Used for | Phase | Reference version |
|---|---|---|---|
| Git | Version control | All | 2.34 |
| Python 3 + `venv` + `pip` | Writing and running watchers locally | 1 | 3.10 (system) — images will ship a current Python |
| Docker Engine | Building and running images | 1–2 | 29.9 |
| Docker Buildx | Multi-arch builds (`linux/arm64` for the server) | 2 | 0.38 |
| Docker Compose | Running watcher + database locally | 1–2 | 5.6 |
| Terraform | Provisioning Oracle Cloud | 3 | 1.17 |
| kubectl | Managing the k3s cluster | 4 | 1.36 (works with clusters 1.35–1.37) |
| `curl`, `jq`, `make`, `unzip` | Scripting and API checks | All | — |

Reference versions are the ones the project was set up with (October 2026). Newer patch releases are fine.

## Install

Every tool is installed from its **official apt repository**, so `sudo apt upgrade` keeps them current:

- Docker Engine: <https://docs.docker.com/engine/install/ubuntu/>
- Terraform: <https://developer.hashicorp.com/terraform/install>
- kubectl (pinned to the `v1.36` repository): <https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/>

Docker Engine runs inside WSL (not Docker Desktop), which requires **systemd**:

```ini
# /etc/wsl.conf
[boot]
systemd=true
```

Then run `wsl --shutdown` from PowerShell and reopen WSL.

After installing Docker, add your user to the `docker` group and open a new terminal:

```bash
sudo usermod -aG docker "$USER"
```

### Troubleshooting

**`docker.service` fails with `no sockets found via socket activation`** — happens when a previous Ubuntu `docker.io` package was removed and left `docker.socket` in a failed state:

```bash
sudo systemctl daemon-reload
sudo systemctl reset-failed docker.service docker.socket
sudo systemctl enable --now docker.socket
sudo systemctl enable --now docker.service
```

## Verify

```bash
docker run --rm hello-world
docker compose version
docker buildx version
terraform version
kubectl version --client
python3 --version
```

## Configure

```bash
git clone https://github.com/borjaviadero/bilbao-flight-deals.git
cd bilbao-flight-deals
cp .env.example .env && chmod 600 .env   # then fill in the values
```

See [telegram-setup.md](telegram-setup.md) for the Telegram values.
