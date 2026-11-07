#!/usr/bin/env bash
# ==============================================================================
# CloudDesk Smoke Test Script (CLAUDE.md §15)
# Validates live endpoint responsiveness post-deployment.
# Usage: ./smoke_test.sh <cloud: aws|azure|gcp> <env: dev|staging|prod> [endpoint_url]
# ==============================================================================

set -euo pipefail

CLOUD="${1:-}"
ENV="${2:-}"
ENDPOINT="${3:-http://localhost:8000}"

if [[ -z "$CLOUD" || -z "$ENV" ]]; then
    echo "Usage: $0 <aws|azure|gcp> <dev|staging|prod> [endpoint_url]" >&2
    exit 1
fi

echo "==> Running smoke tests against $CLOUD ($ENV) at $ENDPOINT..."

# Liveness probe
echo "==> Probing /health/live..."
curl -sf "$ENDPOINT/health/live" || {
    echo "Error: Health live check failed at $ENDPOINT/health/live" >&2
    exit 1
}

# General health
echo "==> Probing /health..."
curl -sf "$ENDPOINT/health" || {
    echo "Error: Health status check failed at $ENDPOINT/health" >&2
    exit 1
}

echo "==> All smoke tests passed successfully for $CLOUD ($ENV)."
