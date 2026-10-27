#!/usr/bin/env bash
# Retry creating the server while Oracle Cloud reports "Out of host capacity".
#
# Ampere A1 (ARM) capacity in a region is sometimes exhausted for hours; the usual fix
# is to keep retrying. Each attempt plans the main stack and applies it WITHOUT asking,
# so for safety it only proceeds when the plan does nothing but create the server
# (1 to add, 0 to change, 0 to destroy). Any other plan, or any other error, stops it.
#
# Usage (from the repository root):   make tf-apply-retry
# Settings: ATTEMPTS (default 60) and WAIT_SECONDS between attempts (default 180).

set -euo pipefail

ATTEMPTS="${ATTEMPTS:-60}"
WAIT_SECONDS="${WAIT_SECONDS:-180}"
STACK="infra/terraform/main"
PLAN_FILE="retry.tfplan"
LOG="$(mktemp)"
trap 'rm -f "$LOG" "$STACK/$PLAN_FILE"' EXIT

tf() { terraform -chdir="$STACK" "$@"; }

for attempt in $(seq 1 "$ATTEMPTS"); do
  echo "[$(date '+%H:%M:%S')] attempt ${attempt}/${ATTEMPTS}"

  tf plan -input=false -no-color -out="$PLAN_FILE" >"$LOG" 2>&1 || {
    cat "$LOG"; echo "Plan failed: stopping."; exit 1
  }
  if grep -q "No changes." "$LOG"; then
    echo "Nothing to do: the server already exists."; tf output; exit 0
  fi
  if ! grep -q "Plan: 1 to add, 0 to change, 0 to destroy." "$LOG" \
     || ! grep -q "oci_core_instance.server will be created" "$LOG"; then
    cat "$LOG"
    echo "The plan does more than create the server: run 'make tf-apply' and review it."
    exit 1
  fi

  if tf apply -input=false -no-color "$PLAN_FILE" >"$LOG" 2>&1; then
    cat "$LOG"; echo "Server created."; exit 0
  fi

  if grep -q "Out of host capacity" "$LOG"; then
    echo "  Out of host capacity. Next attempt in ${WAIT_SECONDS}s (Ctrl+C to stop)."
    sleep "$WAIT_SECONDS"
  else
    cat "$LOG"; echo "Apply failed with another error: stopping."; exit 1
  fi
done

echo "No capacity after ${ATTEMPTS} attempts. Try again later."
exit 1
