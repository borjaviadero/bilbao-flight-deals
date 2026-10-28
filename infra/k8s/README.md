# k8s

Kubernetes manifests for the k3s cluster (Phase 4), applied with Kustomize:

```bash
kubectl apply -k infra/k8s
```

| File | What it is |
|---|---|
| `namespace.yaml` | Namespace `dealhunter`, with Pod Security Admission set to **restricted** |
| `pvc.yaml` | 1 GiB volume for the SQLite history (k3s `local-path` storage) |
| `cronjob-flights-bio.yaml` | The flights watcher, instance `flights-bio`: **09:00 and 21:00 Europe/Madrid**, never two runs at once, one retry, 15 min limit, non-root, read-only root filesystem, no capabilities, CPU/memory limits |
| `kustomization.yaml` | The list above |
| `jobs/dry-run.yaml` | One-off dry run with the same image, secrets and volume (not in the kustomization) |
| `jobs/history-copy.yaml` | Temporary pod used to copy a SQLite history file into the volume |
| `cluster/install-k3s.sh` | Installs the pinned k3s on the server (run over SSH) |

## Secret

Tokens and Telegram IDs go in the Secret `dealhunter-secrets`, created on the cluster from `.env`. It is never committed:

```bash
make k8s-secret   # kubectl create secret generic dealhunter-secrets --from-env-file=.env (idempotent)
```

## Try it locally (k3d)

[k3d](https://k3d.io) runs k3s inside Docker, so the same manifests can be tested on a laptop before the server exists:

```bash
make k8s-local-up     # cluster "dealhunter" in Docker; kubectl context k3d-dealhunter
make k8s-apply        # namespace, volume, CronJob
make k8s-secret       # Secret from .env
make k8s-dry-run      # run once now, print the messages (sends nothing)
make k8s-status       # CronJob, jobs, pods and volume
make k8s-local-down   # delete the local cluster
```

`kubectl create job --from=cronjob/flights-bio now -n dealhunter` triggers a **real** run (it sends alerts).

## On the server (k3s)

The Kubernetes API is **never exposed to the internet**: kubectl reaches it through an SSH tunnel (local port 16443 → server `127.0.0.1:6443`), and the OCI security list still allows only SSH from your IP.

```bash
make k3s-install                         # k3s v1.35.5+k3s1: no ingress/LB, Secrets encrypted at rest
make k3s-kubeconfig                      # ~/.kube/dealhunter-oci.yaml (mode 600)
make k3s-tunnel                          # SSH tunnel in the background
export KUBECONFIG=~/.kube/dealhunter-oci.yaml
make k8s-apply k8s-secret                # same manifests as on k3d
make k8s-import-history                  # copy data/dealhunter.sqlite3 into the volume (once)
make k8s-dry-run                         # check, then wait for 09:00 / 21:00
make k3s-tunnel-stop
```

`install-k3s.sh` also lets pod (10.42.0.0/16) and service (10.43.0.0/16) traffic through the iptables rules of Oracle's Ubuntu image, which otherwise reject everything but SSH. Nothing new is opened to the internet.

CI renders the kustomization and validates every manifest with kubeconform.
