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

CI renders the kustomization and validates every manifest with kubeconform.
