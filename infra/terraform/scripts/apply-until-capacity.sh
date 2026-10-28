#!/usr/bin/env bash
# Retry creating the server while Oracle Cloud reports "Out of host capacity".
#
# Ampere A1 (ARM) capacity in a region is sometimes exhausted for hours; the usual fix
# is to keep retrying. Each attempt plans the main stack and applies it WITHOUT asking,
# so it has three safety checks:
#   1. it only applies when the plan does nothing but create the server
#      (1 to add, 0 to change, 0 to destroy);
#   2. before every attempt it asks OCI whether a server with this name already exists
#      that Terraform does not know about (e.g. a create cut off by a network error),
#      and stops if so, instead of creating a second one;
#   3. any error other than "no capacity" or a transient network error stops it.
# Each attempt uses the next fault domain (1, 2, 3, 1, ...).
#
# Usage (from the repository root):   make tf-apply-retry
# Settings: ATTEMPTS (default 60) and WAIT_SECONDS between attempts (default 180).
# Needs uv (the OCI CLI is run with uvx, downloaded on first use).

set -euo pipefail

ATTEMPTS="${ATTEMPTS:-60}"
WAIT_SECONDS="${WAIT_SECONDS:-180}"
STACK="infra/terraform/main"
PLAN_FILE="retry.tfplan"
FAULT_DOMAINS=(FAULT-DOMAIN-1 FAULT-DOMAIN-2 FAULT-DOMAIN-3)
TRANSIENT='EOF|connection reset|i/o timeout|TLS handshake timeout|context deadline exceeded|502 Bad Gateway|503 Service Unavailable|504 Gateway Timeout'
LOG="$(mktemp)"
trap 'rm -f "$LOG" "$STACK/$PLAN_FILE"' EXIT

tf() { terraform -chdir="$STACK" "$@"; }

tfvar() { # value of a string variable in terraform.tfvars, or $2 if absent
  local value
  value="$(sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*\"\(.*\)\".*/\1/p" "$STACK/terraform.tfvars" | head -n1)"
  echo "${value:-$2}"
}

COMPARTMENT="$(tfvar compartment_ocid "")"
NAME="$(tfvar name dealhunter)"
[[ -n "$COMPARTMENT" ]] || { echo "No compartment_ocid in $STACK/terraform.tfvars (run make tf-main-config)."; exit 1; }

existing_servers() { # servers named $NAME in the compartment that are not terminated
  local count
  count="$(uvx --quiet --from oci-cli oci compute instance list \
    --compartment-id "$COMPARTMENT" --display-name "$NAME" --all \
    --query "length(data[?\"lifecycle-state\"!='TERMINATED'])" --raw-output 2>/dev/null)" || return 1
  echo "${count:-0}" # the CLI prints nothing when the list is empty
}

wait_next() { echo "  $1 Next attempt in ${WAIT_SECONDS}s (Ctrl+C to stop)."; sleep "$WAIT_SECONDS"; }

for attempt in $(seq 1 "$ATTEMPTS"); do
  fd="${FAULT_DOMAINS[$(( (attempt - 1) % 3 ))]}"
  echo "[$(date '+%H:%M:%S')] attempt ${attempt}/${ATTEMPTS} (${fd})"

  if ! tf plan -input=false -no-color -var "fault_domain=${fd}" -out="$PLAN_FILE" >"$LOG" 2>&1; then
    if grep -Eq "$TRANSIENT" "$LOG"; then wait_next "Network error while planning."; continue; fi
    cat "$LOG"; echo "Plan failed: stopping."; exit 1
  fi
  if grep -q "No changes." "$LOG"; then
    echo "Nothing to do: the server already exists."; tf output; exit 0
  fi
  if ! grep -q "Plan: 1 to add, 0 to change, 0 to destroy." "$LOG" \
     || ! grep -q "oci_core_instance.server will be created" "$LOG"; then
    cat "$LOG"
    echo "The plan does more than create the server: run 'make tf-plan' and review it."
    exit 1
  fi

  if ! count="$(existing_servers)"; then
    wait_next "Could not ask OCI for existing servers."; continue
  fi
  if (( count > 0 )); then
    echo "A server named '${NAME}' already exists in OCI but Terraform does not track it"
    echo "(probably a create cut off by a network error). Import it instead of creating"
    echo "another one - see infra/terraform/README.md, 'Untracked server'."
    exit 1
  fi

  if tf apply -input=false -no-color "$PLAN_FILE" >"$LOG" 2>&1; then
    cat "$LOG"; echo "Server created."; exit 0
  fi

  if grep -q "Out of host capacity" "$LOG"; then
    wait_next "Out of host capacity."
  elif grep -Eq "$TRANSIENT" "$LOG"; then
    grep -E "Error:" "$LOG" | head -n 3
    wait_next "Network error while creating; the next attempt first checks that no server was created."
  else
    cat "$LOG"; echo "Apply failed with another error: stopping."; exit 1
  fi
done

echo "No capacity after ${ATTEMPTS} attempts. Try again later."
exit 1
