#!/usr/bin/env bash
# Phase 2 - Task 5: End-to-end ETL & analysis orchestrator with lineage traceability and error traps.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE="ORCHESTRATOR"
ensure_pipeline_dirs

STATUS_JSON="${REPORTS_DIR}/pipeline_status.json"
LINEAGE_JSON="${REPORTS_DIR}/lineage_manifest.json"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CURRENT_STEP="initialization"

write_status_report() {
    local final_status="$1"
    local exit_code="$2"
    local completed_at
    completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    local raw_rows=0
    local clean_rows=0
    local enriched_rows=0
    local rejected_rows=0
    local anomalies_count=0

    if [[ -f "${RAW_DIR}/livraisons.csv" ]]; then
        raw_rows=$(( $(sed '/^[[:space:]]*$/d' "${RAW_DIR}/livraisons.csv" | wc -l) - 1 ))
    fi
    if [[ -f "${PROCESSED_DIR}/livraisons_clean.csv" ]]; then
        clean_rows=$(( $(wc -l < "${PROCESSED_DIR}/livraisons_clean.csv") - 1 ))
    fi
    if [[ -f "${PROCESSED_DIR}/livraisons_enriched.csv" ]]; then
        enriched_rows=$(( $(wc -l < "${PROCESSED_DIR}/livraisons_enriched.csv") - 1 ))
    fi
    if [[ -f "${PROCESSED_DIR}/livraisons_rejected_unix.csv" ]]; then
        rejected_rows=$(( $(wc -l < "${PROCESSED_DIR}/livraisons_rejected_unix.csv") - 1 ))
    fi
    if [[ -f "${REPORTS_DIR}/anomalies.csv" ]]; then
        anomalies_count=$(( $(wc -l < "${REPORTS_DIR}/anomalies.csv") - 1 ))
    fi

    jq -n \
        --arg status "${final_status}" \
        --arg step "${CURRENT_STEP}" \
        --arg started "${STARTED_AT}" \
        --arg completed "${completed_at}" \
        --argjson code "${exit_code}" \
        --argjson raw "${raw_rows}" \
        --argjson clean "${clean_rows}" \
        --argjson enriched "${enriched_rows}" \
        --argjson rejected "${rejected_rows}" \
        --argjson anomalies "${anomalies_count}" \
        '{
            status: $status,
            last_step: $step,
            exit_code: $code,
            started_at: $started,
            completed_at: $completed,
            raw_rows: $raw,
            clean_rows: $clean,
            enriched_rows: $enriched,
            rejected_rows: $rejected,
            anomalies_count: $anomalies
        }' > "${STATUS_JSON}"
}

write_lineage_manifest() {
    local raw_sha="" clean_sha="" enriched_sha=""
    [[ -f "${RAW_DIR}/livraisons.csv" ]] && raw_sha="$(sha256sum "${RAW_DIR}/livraisons.csv" | cut -d' ' -f1)"
    [[ -f "${PROCESSED_DIR}/livraisons_clean.csv" ]] && clean_sha="$(sha256sum "${PROCESSED_DIR}/livraisons_clean.csv" | cut -d' ' -f1)"
    [[ -f "${PROCESSED_DIR}/livraisons_enriched.csv" ]] && enriched_sha="$(sha256sum "${PROCESSED_DIR}/livraisons_enriched.csv" | cut -d' ' -f1)"

    jq -n \
        --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg raw_sha "${raw_sha}" \
        --arg clean_sha "${clean_sha}" \
        --arg enriched_sha "${enriched_sha}" \
        '{
            generated_at: $ts,
            stages: [
                {stage: "raw", file: "data/raw/livraisons.csv", sha256: $raw_sha},
                {stage: "clean_unix", file: "data/processed/livraisons_clean.csv", sha256: $clean_sha},
                {stage: "transform_unix", file: "data/processed/livraisons_enriched.csv", sha256: $enriched_sha}
            ]
        }' > "${LINEAGE_JSON}"
}

on_error() {
    local exit_code=$?
    log_error "${STAGE}" "Pipeline aborted during step '${CURRENT_STEP}' (exit code ${exit_code})."
    write_status_report "FAILED" "${exit_code}"
    exit "${exit_code}"
}

trap on_error ERR

log_info "${STAGE}" "Starting full UNIX data pipeline (DATA_DIR=${DATA_DIR})..."

CURRENT_STEP="clean_data"
"${SCRIPT_DIR}/clean_data.sh"

CURRENT_STEP="transform_data"
"${SCRIPT_DIR}/transform_data.sh"

CURRENT_STEP="analyze_data"
"${PROJECT_DIR}/scripts/analysis/analyze_data.sh"

if [[ -x "${PROJECT_DIR}/.venv/bin/python3" ]]; then
    PYTHON_CMD="${PROJECT_DIR}/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import iragi" >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD=""
fi

if [[ -n "${PYTHON_CMD}" ]]; then
    CURRENT_STEP="iragi_audit"
    log_info "${STAGE}" "Running complementary Iragi quality & reconciliation audit..."
    PYTHONPATH="${PROJECT_DIR}" "${PYTHON_CMD}" -c "
from pathlib import Path
from scripts.etl.audit_quality import run_iragi_audit
run_iragi_audit(
    raw_dir=Path('${RAW_DIR}'),
    processed_dir=Path('${PROCESSED_DIR}'),
    reports_dir=Path('${REPORTS_DIR}'),
)
"
fi

write_lineage_manifest
CURRENT_STEP="completed"
write_status_report "SUCCESS" 0
log_info "${STAGE}" "Pipeline completed successfully. Status saved to ${STATUS_JSON}."
