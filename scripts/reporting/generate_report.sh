#!/usr/bin/env bash
# Phase 3 - Task 3: Generate timestamped Markdown and TailwindCSS HTML reports from real data.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/../etl/common.sh"

STAGE="REPORT"
ensure_pipeline_dirs

for req in "${REPORTS_DIR}/iragi_audit.json" "${REPORTS_DIR}/stats_descriptives.csv" "${PROCESSED_DIR}/agg_par_ville.csv"; do
    if [[ ! -f "${req}" ]]; then
        log_error "${STAGE}" "Missing pipeline analysis artifact: ${req}. Run ./scripts/etl/run_pipeline.sh first."
        exit 2
    fi
done

if [[ -x "${PROJECT_DIR}/.venv/bin/python3" ]]; then
    PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

log_info "${STAGE}" "Generating timestamped Markdown report and HTML dashboard from real data..."
PYTHONPATH="${PROJECT_DIR}" "${PYTHON_BIN}" -c "
from pathlib import Path
import json
from scripts.reporting.render_report import generate_all_reports
from scripts.reporting.update_readme_tree import update_readme_tree
res = generate_all_reports(Path('${DATA_DIR}'))
update_readme_tree(Path('${PROJECT_DIR}'))
print(json.dumps(res, indent=2))
"

log_info "${STAGE}" "Reports written to ${REPORTS_DIR}/latest_report.md and ${REPORTS_DIR}/dashboard_report.html."
