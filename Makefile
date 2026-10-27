# Common development tasks. Run `make help` to list them.
.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test check

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
