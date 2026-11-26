#!/usr/bin/env bash
# Validate required UNIX filters, directory permissions, and optional DB connectivity.

set -euo pipefail
export LC_ALL=C

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_DIR}"

REQUIRED_TOOLS=(bash grep sed awk sort uniq wc cut head tail curl jq python3)
OPTIONAL_CONTAINER_TOOLS=(gnuplot psql shellcheck iragi)

echo "[INFO] Checking mandatory UNIX and Python tools..."
for tool in "${REQUIRED_TOOLS[@]}"; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        echo "[ERROR] Missing mandatory tool: ${tool}" >&2
        exit 1
    fi
done

echo "[INFO] Checking container/extended tools..."
for tool in "${OPTIONAL_CONTAINER_TOOLS[@]}"; do
    if command -v "${tool}" >/dev/null 2>&1; then
        echo "  [OK] ${tool} found"
    else
        echo "  [WARN] ${tool} not in current PATH (expected inside Docker dev container)"
    fi
done

echo "[INFO] Verifying data directory structure and write permissions..."
for subdir in raw processed reports visualizations; do
    target_dir="${PROJECT_DIR}/data/${subdir}"
    mkdir -p "${target_dir}"
    probe_file="${target_dir}/.write_probe_$$"
    touch "${probe_file}"
    rm -f "${probe_file}"
done

if [[ -n "${PGHOST:-}" ]] && command -v pg_isready >/dev/null 2>&1; then
    echo "[INFO] Checking PostgreSQL connectivity on ${PGHOST}:${PGPORT:-5432}..."
    pg_isready -h "${PGHOST}" -p "${PGPORT:-5432}" -U "${PGUSER:-logistics}"
fi

echo "[INFO] Environment validation succeeded."
