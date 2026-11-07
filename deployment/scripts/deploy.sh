#!/usr/bin/env bash
# ==============================================================================
# CloudDesk Deployment Script (CLAUDE.md §15)
# Usage: ./deploy.sh <cloud: aws|azure|gcp> <env: dev|staging|prod> [--auto-approve]
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

# Validate cloud target
if [[ "$CLOUD" != "aws" && "$CLOUD" != "azure" && "$CLOUD" != "gcp" ]]; then
    echo "Error: Invalid cloud target '$CLOUD'. Must be one of: aws, azure, gcp." >&2
    exit 1
fi

# Validate environment
if [[ "$ENV" != "dev" && "$ENV" != "staging" && "$ENV" != "prod" ]]; then
    echo "Error: Invalid environment '$ENV'. Must be one of: dev, staging, prod." >&2
    exit 1
fi

# Security Invariant: Refuse --auto-approve on staging and prod (CLAUDE.md §15, CWE-732)
if [[ "$EXTRA_ARGS" == *"--auto-approve"* || "$*" == *"--auto-approve"* ]]; then
    if [[ "$ENV" == "staging" || "$ENV" == "prod" ]]; then
        echo "Error: --auto-approve is strictly prohibited for '$ENV' environment." >&2
        echo "Safety invariant violation: Automated approval refused by deployment guardrail." >&2
        exit 1
    fi
fi

echo "==> Deploying CloudDesk to $CLOUD ($ENV)..."
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/deployment/$CLOUD"
TFVARS_FILE="$ROOT_DIR/deployment/environments/$ENV/terraform.tfvars"

cd "$TF_DIR"

echo "==> Initializing Terraform..."
terraform init -backend-config="$TF_DIR/backend.hcl" -reconfigure || true

echo "==> Planning deployment..."
terraform plan -var-file="$TFVARS_FILE" -out=tfplan

if [[ "$ENV" == "dev" && ("$EXTRA_ARGS" == *"--auto-approve"* || "$*" == *"--auto-approve"*) ]]; then
    echo "==> Applying deployment with auto-approve (dev only)..."
    terraform apply -auto-approve tfplan
else
    echo "==> Applying deployment plan..."
    terraform apply tfplan
fi

echo "==> Deployment completed successfully."

