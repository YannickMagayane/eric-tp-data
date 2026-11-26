#!/usr/bin/env bash
# Shared constants, directory resolution, and structured logging for UNIX pipelines.

set -euo pipefail
export LC_ALL=C

export PROJECT_DIR
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export DATA_DIR="${DATA_DIR:-${PROJECT_DIR}/data}"
export RAW_DIR="${DATA_DIR}/raw"
export PROCESSED_DIR="${DATA_DIR}/processed"
export REPORTS_DIR="${DATA_DIR}/reports"
export VISUALIZATIONS_DIR="${DATA_DIR}/visualizations"
export PIPELINE_LOG="${REPORTS_DIR}/pipeline.log"

ensure_pipeline_dirs() {
    mkdir -p "${PROCESSED_DIR}" "${REPORTS_DIR}" "${VISUALIZATIONS_DIR}"
}

log_info() {
    local stage="$1"
    local message="$2"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    mkdir -p "${REPORTS_DIR}"
    printf "[%s] [INFO] [%s] %s\n" "${ts}" "${stage}" "${message}" | tee -a "${PIPELINE_LOG}"
}

log_error() {
    local stage="$1"
    local message="$2"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    mkdir -p "${REPORTS_DIR}"
    printf "[%s] [ERROR] [%s] %s\n" "${ts}" "${stage}" "${message}" | tee -a "${PIPELINE_LOG}" >&2
}
