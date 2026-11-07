#!/usr/bin/env bash
# ==============================================================================
# CloudDesk Infrastructure Teardown Script (CLAUDE.md §15)
# Usage: ./destroy.sh <cloud: aws|azure|gcp> <env: dev|staging|prod> [--auto-approve]
# Safety Rule: --auto-approve is strictly REFUSED for staging and prod (CWE-732).
# ==============================================================================

set -euo pipefail

CLOUD="${1:-}"
ENV="${2:-}"
EXTRA_ARGS="${3:-}"

if [[ -z "$CLOUD" || -z "$ENV" ]]; then
    echo "Usage: $0 <aws|azure|gcp> <dev|staging|prod> [--auto-approve]" >&2
    exit 1
fi

# Security Invariant: Refuse --auto-approve on staging and prod (CLAUDE.md §15, CWE-732)
if [[ "$EXTRA_ARGS" == *"--auto-approve"* || "$*" == *"--auto-approve"* ]]; then
    if [[ "$ENV" == "staging" || "$ENV" == "prod" ]]; then
        echo "Error: --auto-approve is strictly prohibited for destroying '$ENV' environment." >&2
        echo "Safety invariant violation: Automated destruction refused by deployment guardrail." >&2
        exit 1
    fi
fi

echo "==> Destroying CloudDesk infrastructure on $CLOUD ($ENV)..."
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/deployment/$CLOUD"
TFVARS_FILE="$ROOT_DIR/deployment/environments/$ENV/terraform.tfvars"

cd "$TF_DIR"

if [[ "$ENV" == "dev" && ("$EXTRA_ARGS" == *"--auto-approve"* || "$*" == *"--auto-approve"*) ]]; then
    terraform destroy -var-file="$TFVARS_FILE" -auto-approve
else
    terraform destroy -var-file="$TFVARS_FILE"
fi

echo "==> Infrastructure destruction completed for $CLOUD ($ENV)."

