#!/usr/bin/env bash
# ==============================================================================
# CloudDesk Rollback Script (CLAUDE.md §15)
# Rolls back container service revision to previous known good git SHA.
# Usage: ./rollback.sh <cloud: aws|azure|gcp> <env: dev|staging|prod> <target_sha>
# ==============================================================================

set -euo pipefail

CLOUD="${1:-}"
ENV="${2:-}"
TARGET_SHA="${3:-}"

if [[ -z "$CLOUD" || -z "$ENV" || -z "$TARGET_SHA" ]]; then
    echo "Usage: $0 <aws|azure|gcp> <dev|staging|prod> <target_git_sha>" >&2
    exit 1
fi

echo "==> Rolling back CloudDesk on $CLOUD ($ENV) to image tag: $TARGET_SHA..."

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/deployment/$CLOUD"
TFVARS_FILE="$ROOT_DIR/deployment/environments/$ENV/terraform.tfvars"

cd "$TF_DIR"

terraform apply -var-file="$TFVARS_FILE" -var="image_tag=$TARGET_SHA"

echo "==> Rollback to $TARGET_SHA completed successfully."

