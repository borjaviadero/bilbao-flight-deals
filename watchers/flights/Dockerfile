# syntax=docker/dockerfile:1
# Container image of the flights watcher.
#
# Build from the repository root (the image needs the shared core and uv.lock):
#   docker build -f watchers/flights/Dockerfile -t flights-watcher .
#
# Two stages: "build" installs the packages with uv into a virtual environment;
# the final stage copies only that environment and the instance configs, and runs
# as a non-root user. Secrets are never baked in: they come from the environment.

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.13.6

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- build stage -------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS build
COPY --from=uv /uv /usr/local/bin/uv

# Compile to bytecode for faster start-up; copy files instead of hard-linking (the
# venv is moved to another stage); use the image's Python, never download one.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src

# 1) Third-party dependencies only, from the lock file. This layer is cached until
#    uv.lock or a pyproject.toml changes, so code edits rebuild in seconds.
COPY pyproject.toml uv.lock ./
COPY core/pyproject.toml core/pyproject.toml
COPY watchers/flights/pyproject.toml watchers/flights/pyproject.toml
RUN uv sync --frozen --no-dev --package flights-watcher --no-install-workspace

# 2) Our own packages, installed as regular (non-editable) packages, so the final
#    image does not need the source tree.
COPY core/ core/
COPY watchers/flights/ watchers/flights/
RUN uv sync --frozen --no-dev --package flights-watcher --no-editable

# --- runtime stage -----------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="flights-watcher" \
      org.opencontainers.image.description="Watches round-trip flight prices and alerts on Telegram." \
      org.opencontainers.image.source="https://github.com/borjaviadero/bilbao-flight-deals" \
      org.opencontainers.image.licenses="MIT"

# Time-zone database for Europe/Madrid (dates in messages and the deal windows).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# Unprivileged user; /data holds the SQLite history and must be writable by it.
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data \
    && chown app:app /data

COPY --from=build /app/.venv /app/.venv
COPY config/ /app/config/

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    DEALHUNTER_DB_PATH=/data/dealhunter.sqlite3

WORKDIR /app
USER app
VOLUME ["/data"]

ENTRYPOINT ["python", "-m", "flights_watcher"]
CMD ["run", "--config", "config/watchers/flights-bio.yaml"]
