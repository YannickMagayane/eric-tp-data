#!/usr/bin/env bash
# Phase 2 - Task 2: UNIX cleaning pipeline using sed, sort, uniq, awk, and jq.
# Enforces 14-column delivery schema, 9 French cities, and row-count conservation checks.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE="CLEAN"
ensure_pipeline_dirs

for required_raw in "${RAW_DIR}/livraisons.csv" "${RAW_DIR}/livreurs.json" "${RAW_DIR}/access.log"; do
    if [[ ! -f "${required_raw}" ]]; then
        log_error "${STAGE}" "Missing raw input file: ${required_raw}"
        exit 2
    fi
done

log_info "${STAGE}" "Cleaning livraisons.csv with sed, sort | uniq, and awk validation..."

CLEAN_DELIVERIES="${PROCESSED_DIR}/livraisons_clean.csv"
REJECTED_DELIVERIES="${PROCESSED_DIR}/livraisons_rejected_unix.csv"
TMP_DEDUP="${PROCESSED_DIR}/.tmp_livraisons_dedup.csv"
TMP_VALID="${PROCESSED_DIR}/.tmp_livraisons_valid.csv"

echo "id,date,ville,livreur_id,poids,distance,temps,temps_prevu,statut,type_livraison,type_client,type_vehicule,cout_livraison,zone_livraison,reason" > "${REJECTED_DELIVERIES}"

raw_non_empty=$(tail -n +2 "${RAW_DIR}/livraisons.csv" | sed '/^[[:space:]]*$/d' | wc -l)

tail -n +2 "${RAW_DIR}/livraisons.csv" \
    | sed '/^[[:space:]]*$/d' \
    | sed -E 's/[[:space:]]*,[[:space:]]*/,/g; s/^[[:space:]]+//; s/[[:space:]]+$//' \
    | sort \
    | uniq > "${TMP_DEDUP}"

dedup_rows=$(wc -l < "${TMP_DEDUP}")
dedup_removed=$(( raw_non_empty - dedup_rows ))

awk -F',' -v rejected="${REJECTED_DELIVERIES}" '
    BEGIN {
        OFS = ","
        split("Paris,Lyon,Marseille,Lille,Bordeaux,Toulouse,Nantes,Nice,Strasbourg", c_arr, ",")
        for (i in c_arr) valid_city[c_arr[i]] = 1
        split("livre,en_cours,retarde,annule", s_arr, ",")
        for (i in s_arr) valid_status[s_arr[i]] = 1
        split("Velo,Moto,Camionnette,Fourgon", v_arr, ",")
        for (i in v_arr) valid_vehicle[v_arr[i]] = 1
    }
    {
        if (NF != 14) {
            print $0, "column_count_mismatch" >> rejected
            next
        }
        id = $1; dt = $2; city = $3; cid = $4; w = $5; dist = $6
        dur = $7; plan = $8; st = $9; tdel = $10; tcli = $11; veh = $12; cost = $13; zone = $14

        if (id == "" || dt == "" || city == "" || cid == "" || w == "" || dist == "" || dur == "" || plan == "" || st == "" || cost == "") {
            print $0, "missing_value" >> rejected
            next
        }
        if (id !~ /^[0-9]+$/ || (id + 0) <= 0 || cid !~ /^[0-9]+$/ || (cid + 0) <= 0) {
            print $0, "invalid_id" >> rejected
            next
        }
        if (dt !~ /^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$/) {
            print $0, "invalid_date" >> rejected
            next
        }
        if (!(city in valid_city)) {
            print $0, "invalid_city" >> rejected
            next
        }
        if (w !~ /^[0-9]+(\.[0-9]+)?$/ || (w + 0.0) < 5.0 || (w + 0.0) > 50.0) {
            print $0, "weight_out_of_range" >> rejected
            next
        }
        if (dist !~ /^[0-9]+$/ || (dist + 0) < 10 || (dist + 0) > 500) {
            print $0, "distance_out_of_range" >> rejected
            next
        }
        if (dur !~ /^[0-9]+$/ || (dur + 0) < 30 || (dur + 0) > 300 || plan !~ /^[0-9]+$/ || (plan + 0) < 30 || (plan + 0) > 300) {
            print $0, "duration_out_of_range" >> rejected
            next
        }
        if (!(st in valid_status)) {
            print $0, "invalid_status" >> rejected
            next
        }
        if (!(veh in valid_vehicle)) {
            print $0, "invalid_vehicle" >> rejected
            next
        }
        if (cost !~ /^[0-9]+(\.[0-9]+)?$/ || (cost + 0.0) <= 0) {
            print $0, "invalid_cost" >> rejected
            next
        }
        if (seen_id[id]++) {
            print $0, "duplicate_id" >> rejected
            next
        }
        printf "%d,%s,%s,%d,%.2f,%d,%d,%d,%s,%s,%s,%s,%.2f,%s\n",
            id, dt, city, cid, w, dist, dur, plan, st, tdel, tcli, veh, cost, zone
    }
' "${TMP_DEDUP}" > "${TMP_VALID}"

{
    echo "id,date,ville,livreur_id,poids,distance,temps,temps_prevu,statut,type_livraison,type_client,type_vehicule,cout_livraison,zone_livraison"
    sort -t',' -k1,1n "${TMP_VALID}"
} > "${CLEAN_DELIVERIES}"
rm -f "${TMP_DEDUP}" "${TMP_VALID}"

clean_count=$(( $(wc -l < "${CLEAN_DELIVERIES}") - 1 ))
rejected_count=$(( $(wc -l < "${REJECTED_DELIVERIES}") - 1 ))

# Row-count conservation check: zero silent data loss allowed
if [[ $(( clean_count + rejected_count )) -ne "${dedup_rows}" ]]; then
    log_error "${STAGE}" "Row conservation failed: clean(${clean_count}) + rejected(${rejected_count}) != dedup(${dedup_rows})"
    exit 4
fi

log_info "${STAGE}" "Extracting and validating livreurs.json with jq..."
CLEAN_COURIERS="${PROCESSED_DIR}/livreurs_clean.csv"
{
    echo "id,nom,ville,experience,note,vehicule,statut"
    jq -r '
        sort_by(.id)[]
        | select(.id != null and .nom != null and .ville != null)
        | [.id, .nom, .ville, .experience, .note, .vehicule, .statut]
        | @csv
    ' "${RAW_DIR}/livreurs.json" | sed 's/"//g'
} > "${CLEAN_COURIERS}"

log_info "${STAGE}" "Parsing Apache access.log with sed and awk..."
CLEAN_LOGS="${PROCESSED_DIR}/access_clean.csv"
{
    echo "ip,timestamp,method,endpoint,http_status,bytes"
    sed '/^[[:space:]]*$/d' "${RAW_DIR}/access.log" \
        | awk '{
            ip = $1
            ts = substr($4, 2) " " substr($5, 1, length($5) - 1)
            method = substr($6, 2)
            endpoint = $7
            status = $9
            bytes = $10
            if (status ~ /^[0-9]{3}$/ && bytes ~ /^[0-9]+$/) {
                printf "%s,%s,%s,%s,%d,%d\n", ip, ts, method, endpoint, status, bytes
            }
        }'
} > "${CLEAN_LOGS}"

log_info "${STAGE}" "Completed: raw_non_empty=${raw_non_empty}, dedup_removed=${dedup_removed}, clean=${clean_count}, rejected=${rejected_count}."
