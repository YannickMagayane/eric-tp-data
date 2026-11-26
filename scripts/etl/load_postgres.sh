#!/usr/bin/env bash
# Phase 3 - Task 2: Load cleaned and enriched datasets into PostgreSQL for Metabase.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE="LOAD_DB"
ensure_pipeline_dirs

COURIERS_CSV="${PROCESSED_DIR}/livreurs_clean.csv"
ENRICHED_CSV="${PROCESSED_DIR}/livraisons_enriched.csv"
LOGS_CSV="${PROCESSED_DIR}/access_clean.csv"
SCHEMA_SQL="${PROJECT_DIR}/sql/schema.sql"

for req in "${COURIERS_CSV}" "${ENRICHED_CSV}" "${LOGS_CSV}" "${SCHEMA_SQL}"; do
    if [[ ! -f "${req}" ]]; then
        log_error "${STAGE}" "Missing required file for PostgreSQL load: ${req}"
        exit 2
    fi
done

if [[ "${1:-}" == "--validate-only" ]]; then
    log_info "${STAGE}" "Input CSV files and SQL schema validated for PostgreSQL loading."
    exit 0
fi

TMP_DELIVERIES_DB="${PROCESSED_DIR}/.tmp_deliveries_db.csv"
cut -d',' -f1,2,4,5,6,7,8,9 "${ENRICHED_CSV}" > "${TMP_DELIVERIES_DB}"

run_psql() {
    if [[ -n "${PGHOST:-}" ]]; then
        psql -v ON_ERROR_STOP=1 -h "${PGHOST}" -p "${PGPORT:-5432}" \
            -U "${PGUSER:-logistics}" -d "${PGDATABASE:-logistics_db}" "$@"
    elif command -v docker >/dev/null 2>&1 && docker compose ps --status running 2>/dev/null | grep -q "db"; then
        docker compose exec -T db psql -v ON_ERROR_STOP=1 \
            -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" "$@"
    else
        rm -f "${TMP_DELIVERIES_DB}"
        log_error "${STAGE}" "PostgreSQL service is not reachable (start stack with ./bin/launch.sh)."
        exit 3
    fi
}

log_info "${STAGE}" "Applying schema and loading cleaned tables into PostgreSQL..."
run_psql < "${SCHEMA_SQL}"
run_psql -c "TRUNCATE TABLE couriers, deliveries, web_access_logs RESTART IDENTITY;"

if [[ -n "${PGHOST:-}" ]]; then
    run_psql -c "\copy couriers(id,nom,ville,experience,note,vehicule) FROM '${COURIERS_CSV}' WITH (FORMAT csv, HEADER true)"
    run_psql -c "\copy deliveries(id,delivery_date,ville,poids,distance,temps,statut,speed_kmh) FROM '${TMP_DELIVERIES_DB}' WITH (FORMAT csv, HEADER true)"
    run_psql -c "\copy web_access_logs(client_ip,logged_at,http_method,endpoint,http_status,response_bytes) FROM '${LOGS_CSV}' WITH (FORMAT csv, HEADER true)"
else
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy couriers(id,nom,ville,experience,note,vehicule) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${COURIERS_CSV}"
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy deliveries(id,delivery_date,ville,poids,distance,temps,statut,speed_kmh) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${TMP_DELIVERIES_DB}"
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy web_access_logs(client_ip,logged_at,http_method,endpoint,http_status,response_bytes) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${LOGS_CSV}"
fi

rm -f "${TMP_DELIVERIES_DB}"
log_info "${STAGE}" "PostgreSQL tables couriers, deliveries, and web_access_logs successfully populated."
