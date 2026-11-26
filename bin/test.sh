#!/usr/bin/env bash
# Execute isolated Python tests (pytest) and static shell analysis (shellcheck).

set -euo pipefail
export LC_ALL=C

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

if [[ -x ".venv/bin/pytest" ]]; then
    PYTEST_BIN=".venv/bin/pytest"
elif command -v pytest >/dev/null 2>&1; then
    PYTEST_BIN="pytest"
else
    echo "[ERROR] pytest is not installed." >&2
    exit 1
fi

echo "[INFO] Running pytest suite..."
"${PYTEST_BIN}" tests/ -v

if command -v shellcheck >/dev/null 2>&1; then
    echo "[INFO] Running shellcheck on shell scripts..."
    shellcheck -x bin/*.sh scripts/etl/*.sh scripts/analysis/*.sh
else
    echo "[INFO] shellcheck not installed on host (available inside Docker dev image)."
fi
