# Common development tasks. Run `make help` to list them.
.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test check search dry-run run \
	docker-build docker-dry-run docker-run docker-import-history \
	tf-fmt tf-bootstrap-init tf-bootstrap-plan tf-bootstrap-apply

help:  ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-22s %s\n", $$1, $$2}'

install:  ## Create the virtual environment and install all packages
	uv sync

lint:  ## Check code style (no changes)
	uv run ruff check .
	uv run ruff format --check .

format:  ## Fix code style automatically
	uv run ruff format .
	uv run ruff check --fix .

typecheck:  ## Static type checking
	uv run mypy core/src watchers/flights/src

test:  ## Run the test suite
	uv run pytest

check: lint typecheck test  ## Everything a pull request must pass

INSTANCE ?= flights-bio

search:  ## List fares that pass the filters for INSTANCE (read-only; needs .env)
	@test -f .env || { echo "Missing .env - copy .env.example and fill it in"; exit 1; }
	set -a && . ./.env && set +a && \
	uv run python -m flights_watcher search --config config/watchers/$(INSTANCE).yaml

dry-run:  ## Full run for INSTANCE, printing the messages; sends and stores nothing
	@test -f .env || { echo "Missing .env - copy .env.example and fill it in"; exit 1; }
	set -a && . ./.env && set +a && \
	uv run python -m flights_watcher run --config config/watchers/$(INSTANCE).yaml --dry-run

run:  ## Full run for INSTANCE: records history and sends Telegram messages
	@test -f .env || { echo "Missing .env - copy .env.example and fill it in"; exit 1; }
	set -a && . ./.env && set +a && \
	uv run python -m flights_watcher run --config config/watchers/$(INSTANCE).yaml

# --- Docker (Phase 2) -------------------------------------------------------------
# The same runs, inside the container image. Secrets come from .env at run time
# (never baked into the image); the history lives in the named volume $(VOLUME).

IMAGE ?= flights-watcher:dev
VOLUME ?= dealhunter-data
DOCKER_RUN = docker run --rm --env-file .env -v $(VOLUME):/data $(IMAGE)

docker-build:  ## Build the flights watcher image as IMAGE
	docker build -f watchers/flights/Dockerfile -t $(IMAGE) .

docker-dry-run:  ## Dry run for INSTANCE inside the image (sends and stores nothing)
	@test -f .env || { echo "Missing .env - copy .env.example and fill it in"; exit 1; }
	$(DOCKER_RUN) run --config config/watchers/$(INSTANCE).yaml --dry-run

docker-run:  ## Full run for INSTANCE inside the image (history in the Docker volume)
	@test -f .env || { echo "Missing .env - copy .env.example and fill it in"; exit 1; }
	$(DOCKER_RUN) run --config config/watchers/$(INSTANCE).yaml

docker-import-history:  ## Copy data/dealhunter.sqlite3 into the Docker volume (once)
	@test -f data/dealhunter.sqlite3 || { echo "No local history in data/"; exit 1; }
	docker run --rm -v $(VOLUME):/data -v "$(CURDIR)/data:/src:ro" --entrypoint cp \
		$(IMAGE) /src/dealhunter.sqlite3 /data/dealhunter.sqlite3

# --- Terraform (Phase 3) ----------------------------------------------------------
# Credentials come from ~/.oci/config; inputs from terraform.tfvars (ignored by Git).

TF_BOOTSTRAP = terraform -chdir=infra/terraform/bootstrap

tf-fmt:  ## Format every Terraform file
	terraform fmt -recursive infra/terraform

tf-bootstrap-init:  ## Download the OCI provider for the bootstrap stack
	$(TF_BOOTSTRAP) init

tf-bootstrap-plan:  ## Show what the bootstrap stack would create (changes nothing)
	$(TF_BOOTSTRAP) plan

tf-bootstrap-apply:  ## Create the compartment, state bucket and budget (asks to confirm)
	$(TF_BOOTSTRAP) apply

# --- Kubernetes (Phase 4) ---------------------------------------------------------
# Uses the current kubectl context: k3d-dealhunter locally, the server later.

.PHONY: k8s-local-up k8s-local-down k8s-apply k8s-secret k8s-dry-run k8s-status

K8S_NS = dealhunter
K3D_CLUSTER ?= dealhunter

k8s-local-up:  ## Create a local k3s cluster in Docker with k3d (for testing)
	k3d cluster create $(K3D_CLUSTER) --wait

k8s-local-down:  ## Delete the local k3d cluster
	k3d cluster delete $(K3D_CLUSTER)

k8s-apply:  ## Apply the manifests in infra/k8s (namespace, volume, CronJob)
	kubectl apply -k infra/k8s

k8s-secret:  ## Create or update the Secret dealhunter-secrets from .env
	@test -f .env || { echo "Missing .env - copy .env.example and fill it in"; exit 1; }
	kubectl -n $(K8S_NS) create secret generic dealhunter-secrets --from-env-file=.env \
		--dry-run=client -o yaml | kubectl apply -f -

k8s-dry-run:  ## Run the watcher once now in the cluster, in dry-run mode, and show its output
	@job=$$(kubectl create -f infra/k8s/jobs/dry-run.yaml -o name) && echo "$$job" && \
	kubectl -n $(K8S_NS) wait --for=condition=complete --timeout=600s $$job; \
	kubectl -n $(K8S_NS) logs $$job

k8s-status:  ## Show the CronJob, recent jobs, pods and the volume
	kubectl -n $(K8S_NS) get cronjob,job,pod,pvc

# --- k3s on the server (Phase 4) --------------------------------------------------
# The Kubernetes API is never exposed: kubectl reaches it through an SSH tunnel
# (local port 16443 -> server 127.0.0.1:6443).

.PHONY: k3s-install k3s-kubeconfig k3s-tunnel k3s-tunnel-stop k8s-import-history

SERVER_IP = $(shell terraform -chdir=infra/terraform/main output -raw public_ip 2>/dev/null)
SERVER_SSH = ssh -i ~/.ssh/oci_dealhunter -o StrictHostKeyChecking=accept-new ubuntu@$(SERVER_IP)
OCI_KUBECONFIG = $(HOME)/.kube/dealhunter-oci.yaml

k3s-install:  ## Install the pinned k3s on the server (over SSH)
	@test -n "$(SERVER_IP)" || { echo "No server IP: is the main Terraform stack applied?"; exit 1; }
	$(SERVER_SSH) 'sudo bash -s' < infra/k8s/cluster/install-k3s.sh

k3s-kubeconfig:  ## Save the server's kubeconfig as ~/.kube/dealhunter-oci.yaml (via the tunnel)
	@mkdir -p $(HOME)/.kube
	$(SERVER_SSH) 'sudo cat /etc/rancher/k3s/k3s.yaml' \
		| sed -e 's#https://127.0.0.1:6443#https://127.0.0.1:16443#' -e 's/\bdefault$$/dealhunter-oci/' \
		> $(OCI_KUBECONFIG)
	@chmod 600 $(OCI_KUBECONFIG)
	@echo "Saved $(OCI_KUBECONFIG). Use it with: export KUBECONFIG=$(OCI_KUBECONFIG)"

k3s-tunnel:  ## Open the SSH tunnel to the server's Kubernetes API in the background
	$(SERVER_SSH) -f -N -o ExitOnForwardFailure=yes -L 16443:127.0.0.1:6443
	@echo "Tunnel open on 127.0.0.1:16443 (stop it with: make k3s-tunnel-stop)"

k3s-tunnel-stop:  ## Close the SSH tunnel
	-pkill -f "16443:127.0.0.1:6443"

k8s-import-history:  ## Copy data/dealhunter.sqlite3 into the cluster's history volume (once)
	@test -f data/dealhunter.sqlite3 || { echo "No local history in data/"; exit 1; }
	kubectl apply -f infra/k8s/jobs/history-copy.yaml
	kubectl -n $(K8S_NS) wait --for=condition=Ready pod/history-copy --timeout=180s
	kubectl cp data/dealhunter.sqlite3 $(K8S_NS)/history-copy:/data/dealhunter.sqlite3
	kubectl -n $(K8S_NS) exec history-copy -- ls -l /data
	kubectl -n $(K8S_NS) delete pod history-copy --wait=false
