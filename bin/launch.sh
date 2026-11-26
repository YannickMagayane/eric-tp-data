#!/usr/bin/env bash
# Launch Docker environment with Traefik, PostgreSQL, Metabase, and dev container.

set -euo pipefail
export LC_ALL=C

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

echo "[INFO] Validating docker-compose configuration..."
docker compose config -q

echo "[INFO] Building and starting services..."
docker compose up -d --build

echo "[INFO] Validating runtime environment inside dev container..."
docker compose exec -T dev ./scripts/etl/validate_env.sh

echo "[INFO] Stack ready. Metabase routed via Traefik at http://metabase.localhost:${TRAEFIK_HTTP_PORT:-8080}"
