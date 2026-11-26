#!/usr/bin/env bash
# Phase 3 - Task 2: Load cleaned 14-column datasets and Iragi audit metrics into PostgreSQL for Metabase.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE="LOAD_DB"
ensure_pipeline_dirs

COURIERS_CSV="${PROCESSED_DIR}/livreurs_clean.csv"
ENRICHED_CSV="${PROCESSED_DIR}/livraisons_enriched.csv"
LOGS_CSV="${PROCESSED_DIR}/access_clean.csv"
IRAGI_DAT="${PROCESSED_DIR}/iragi_before_after.dat"
IRAGI_JSON="${REPORTS_DIR}/iragi_audit.json"
SCHEMA_SQL="${PROJECT_DIR}/sql/schema.sql"

for req in "${COURIERS_CSV}" "${ENRICHED_CSV}" "${LOGS_CSV}" "${IRAGI_DAT}" "${IRAGI_JSON}" "${SCHEMA_SQL}"; do
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
TMP_IRAGI_DB="${PROCESSED_DIR}/.tmp_iragi_db.csv"

cut -d',' -f1,2,4,5,6,7,8,9,10,11,12,13,14,15,16,17 "${ENRICHED_CSV}" > "${TMP_DELIVERIES_DB}"

score_avant="$(jq -r '.raw_quality_score' "${IRAGI_JSON}")"
score_apres="$(jq -r '.clean_quality_score' "${IRAGI_JSON}")"
dlq_count="$(jq -r '.quarantined_rows_count' "${IRAGI_JSON}")"
orphans_http="$(jq -r '.orphan_http_delivery_calls' "${IRAGI_JSON}")"
{
    echo "categorie,donnees_brutes,approche_classique_naive,pipeline_unix_iragi,score_avant,score_apres,quarantaine_dlq,orphelins_http_404"
    tail -n +2 "${IRAGI_DAT}" \
        | sed 's/"//g' \
        | awk -F'\t' -v sa="${score_avant}" -v sp="${score_apres}" -v dlq="${dlq_count}" -v orp="${orphans_http}" \
            '{ printf "%s,%d,%d,%d,%.2f,%.2f,%d,%d\n", $1, $2, $3, $4, sa, sp, dlq, orp }'
} > "${TMP_IRAGI_DB}"

run_psql() {
    if [[ -n "${PGHOST:-}" ]]; then
        psql -v ON_ERROR_STOP=1 -h "${PGHOST}" -p "${PGPORT:-5432}" \
            -U "${PGUSER:-logistics}" -d "${PGDATABASE:-logistics_db}" "$@"
    elif command -v docker >/dev/null 2>&1 && docker compose ps --status running 2>/dev/null | grep -q "db"; then
        docker compose exec -T db psql -v ON_ERROR_STOP=1 \
            -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" "$@"
    else
        rm -f "${TMP_DELIVERIES_DB}" "${TMP_IRAGI_DB}"
        log_error "${STAGE}" "PostgreSQL service is not reachable (start stack with ./bin/launch.sh)."
        exit 3
    fi
}

log_info "${STAGE}" "Recreating schema and loading cleaned tables into PostgreSQL..."
run_psql -c "DROP TABLE IF EXISTS deliveries, couriers, web_access_logs, iragi_audit_metrics CASCADE;"
run_psql < "${SCHEMA_SQL}"

if [[ -n "${PGHOST:-}" ]]; then
    run_psql -c "\copy couriers(id,nom,ville,experience,note,vehicule,statut) FROM '${COURIERS_CSV}' WITH (FORMAT csv, HEADER true)"
    run_psql -c "\copy deliveries(id,delivery_date,ville,livreur_id,poids,distance,temps,temps_prevu,statut,type_livraison,type_client,type_vehicule,cout_livraison,zone_livraison,speed_kmh,ecart_temps) FROM '${TMP_DELIVERIES_DB}' WITH (FORMAT csv, HEADER true)"
    run_psql -c "\copy web_access_logs(client_ip,logged_at,http_method,endpoint,http_status,response_bytes) FROM '${LOGS_CSV}' WITH (FORMAT csv, HEADER true)"
    run_psql -c "\copy iragi_audit_metrics(categorie,donnees_brutes,approche_classique_naive,pipeline_unix_iragi,score_avant,score_apres,quarantaine_dlq,orphelins_http_404) FROM '${TMP_IRAGI_DB}' WITH (FORMAT csv, HEADER true)"
else
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy couriers(id,nom,ville,experience,note,vehicule,statut) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${COURIERS_CSV}"
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy deliveries(id,delivery_date,ville,livreur_id,poids,distance,temps,temps_prevu,statut,type_livraison,type_client,type_vehicule,cout_livraison,zone_livraison,speed_kmh,ecart_temps) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${TMP_DELIVERIES_DB}"
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy web_access_logs(client_ip,logged_at,http_method,endpoint,http_status,response_bytes) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${LOGS_CSV}"
    docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-logistics}" -d "${POSTGRES_DB:-logistics_db}" \
        -c "\copy iragi_audit_metrics(categorie,donnees_brutes,approche_classique_naive,pipeline_unix_iragi,score_avant,score_apres,quarantaine_dlq,orphelins_http_404) FROM STDIN WITH (FORMAT csv, HEADER true)" < "${TMP_IRAGI_DB}"
fi

rm -f "${TMP_DELIVERIES_DB}" "${TMP_IRAGI_DB}"
log_info "${STAGE}" "PostgreSQL tables couriers, deliveries, web_access_logs, and iragi_audit_metrics populated."
