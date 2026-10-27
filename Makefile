# Common development tasks. Run `make help` to list them.
.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test check search dry-run run

help:  ## Show this help
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

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
