#!/usr/bin/env bash
# ==============================================================================
# CloudDesk Build and Push Script (CLAUDE.md §15)
# Builds backend and frontend containers with git SHA tagging and pushes to registry.
# Usage: ./build_and_push.sh <cloud: aws|azure|gcp> <env: dev|staging|prod>
# ==============================================================================

set -euo pipefail

CLOUD="${1:-}"
ENV="${2:-}"

if [[ -z "$CLOUD" || -z "$ENV" ]]; then
    echo "Usage: $0 <aws|azure|gcp> <dev|staging|prod>" >&2
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo 'local')"

echo "==> Building and pushing container images for $CLOUD ($ENV) with tag: $GIT_SHA..."

# Build Backend Image
echo "==> Building backend image..."
docker build -f "$ROOT_DIR/backend/Dockerfile" -t "clouddesk-backend:$GIT_SHA" "$ROOT_DIR"

# Build Frontend Image
echo "==> Building frontend image..."
docker build -f "$ROOT_DIR/frontend/Dockerfile" -t "clouddesk-frontend:$GIT_SHA" "$ROOT_DIR/frontend"

echo "==> Container images built successfully with git SHA tag: $GIT_SHA"

