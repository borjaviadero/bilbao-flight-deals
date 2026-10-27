# Common development tasks. Run `make help` to list them.
.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test check search dry-run run \
	docker-build docker-dry-run docker-run docker-import-history \
	tf-fmt tf-bootstrap-init tf-bootstrap-plan tf-bootstrap-apply \
	tf-main-config tf-init tf-plan tf-apply tf-ssh

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

TF_MAIN = terraform -chdir=infra/terraform/main

tf-main-config:  ## Write main/backend.hcl and main/terraform.tfvars (bootstrap outputs + your IP)
	$(TF_BOOTSTRAP) output -raw backend_config > infra/terraform/main/backend.hcl
	echo "region    = \"$$(grep '^region=' ~/.oci/config | cut -d= -f2)\"" >> infra/terraform/main/backend.hcl
	printf 'compartment_ocid = "%s"\nadmin_cidr       = "%s/32"\n' \
		"$$($(TF_BOOTSTRAP) output -raw compartment_ocid)" \
		"$$(curl -4 -fsS https://api.ipify.org)" > infra/terraform/main/terraform.tfvars
	@echo "Wrote infra/terraform/main/backend.hcl and terraform.tfvars"

tf-init:  ## Initialise the main stack (state in the OCI bucket)
	$(TF_MAIN) init -backend-config=backend.hcl

tf-plan:  ## Show what the main stack would change (changes nothing)
	$(TF_MAIN) plan

tf-apply:  ## Create or update the network and the server (asks to confirm)
	$(TF_MAIN) apply

tf-ssh:  ## Log in to the server over SSH
	$$($(TF_MAIN) output -raw ssh_command)
