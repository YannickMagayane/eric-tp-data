#!/usr/bin/env bash
# Phase 3 - Task 2: Load cleaned and enriched 14-column datasets into PostgreSQL for Metabase.

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
# Select columns matching sql/schema.sql deliveries table:
# id(1), date(2), ville(4), livreur_id(5), poids(6), distance(7), temps(8), temps_prevu(9),
# statut(10), type_livraison(11), type_client(12), type_vehicule(13), cout_livraison(14),
# zone_livraison(15), speed_kmh(16), ecart_temps(17)
cut -d',' -f1,2,4,5,6,7,8,9,10,11,12,13,14,15,16,17 "${ENRICHED_CSV}" > "${TMP_DELIVERIES_DB}"

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

log_info "${STAGE}" "Recreating schema and loading cleaned tables into PostgreSQL..."
run_psql -c "DROP TABLE IF EXISTS deliveries, couriers, web_access_logs CASCADE;"
run_psql < "${SCHEMA_SQL}"

if [[ -n "${PGHOST:-}" ]]; then
    run_psql -c "\copy couriers(id,nom,ville,experience,note,vehicule,statut) FROM '${COURIERS_CSV}' WITH (FORMAT csv, HEADER true)"
    run_psql -c "\copy deliveries(id,delivery_date,ville,livreur_id,poids,distance,temps,temps_prevu,statut,type_livraison,type_client,type_vehicule,cout_livraison,zone_livraison,speed_kmh,ecart_temps) FROM '${TMP_DELIVERIES_DB}' WITH (FORMAT csv, HEADER true)"
    run_psql -c "\copy web_access_logs(client_ip,logged_at,http_method,endpoint,http_status,response_bytes) FROM '${LOGS_CSV}' WITH (FORMAT csv, HEADER true)"
else
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy couriers(id,nom,ville,experience,note,vehicule,statut) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${COURIERS_CSV}"
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy deliveries(id,delivery_date,ville,livreur_id,poids,distance,temps,temps_prevu,statut,type_livraison,type_client,type_vehicule,cout_livraison,zone_livraison,speed_kmh,ecart_temps) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${TMP_DELIVERIES_DB}"
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy web_access_logs(client_ip,logged_at,http_method,endpoint,http_status,response_bytes) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${LOGS_CSV}"
fi

rm -f "${TMP_DELIVERIES_DB}"
log_info "${STAGE}" "PostgreSQL tables couriers, deliveries, and web_access_logs successfully populated."
