#!/usr/bin/env bash
# Phase 2 - Task 3: UNIX transformation pipeline using awk, sort, join, and jq.
# Joins deliveries with courier profiles on livreur_id and aggregates across cities, months, statuses, and vehicles.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE="TRANSFORM"
ensure_pipeline_dirs

CLEAN_DELIVERIES="${PROCESSED_DIR}/livraisons_clean.csv"
CLEAN_COURIERS="${PROCESSED_DIR}/livreurs_clean.csv"

for req in "${CLEAN_DELIVERIES}" "${CLEAN_COURIERS}"; do
    if [[ ! -f "${req}" ]]; then
        log_error "${STAGE}" "Missing cleaned input file: ${req}"
        exit 2
    fi
done

log_info "${STAGE}" "Computing derived columns and joining deliveries with couriers via UNIX join..."

TMP_COURIERS_KEYED="${PROCESSED_DIR}/.tmp_couriers_keyed.csv"
TMP_DERIVED="${PROCESSED_DIR}/.tmp_derived_deliveries.csv"
TMP_JOINED="${PROCESSED_DIR}/.tmp_joined_deliveries.csv"
ENRICHED_CSV="${PROCESSED_DIR}/livraisons_enriched.csv"

tail -n +2 "${CLEAN_COURIERS}" | sort -t',' -k1,1 > "${TMP_COURIERS_KEYED}"

# Derive speed_kmh, ecart_temps (temps - temps_prevu), and year_month; sort on column 4 (livreur_id)
tail -n +2 "${CLEAN_DELIVERIES}" \
    | awk -F',' '
        {
            speed = ($6 * 60.0) / $7
            ecart = $7 - $8
            ym = substr($2, 1, 7)
            printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%.2f,%d,%s\n",
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, speed, ecart, ym
        }
    ' \
    | sort -t',' -k4,4 > "${TMP_DERIVED}"

join -t',' -a 1 -e 'UNKNOWN' -1 4 -2 1 \
    -o 1.1,1.2,1.17,1.3,1.4,1.5,1.6,1.7,1.8,1.9,1.10,1.11,1.12,1.13,1.14,1.15,1.16,2.2,2.4,2.5 \
    "${TMP_DERIVED}" "${TMP_COURIERS_KEYED}" \
    | sort -t',' -k1,1n > "${TMP_JOINED}"

{
    echo "id,date,year_month,ville,livreur_id,poids,distance,temps,temps_prevu,statut,type_livraison,type_client,type_vehicule,cout_livraison,zone_livraison,speed_kmh,ecart_temps,courier_nom,courier_experience,courier_note"
    cat "${TMP_JOINED}"
} > "${ENRICHED_CSV}"

rm -f "${TMP_COURIERS_KEYED}" "${TMP_DERIVED}" "${TMP_JOINED}"

clean_rows=$(( $(wc -l < "${CLEAN_DELIVERIES}") - 1 ))
enriched_rows=$(( $(wc -l < "${ENRICHED_CSV}") - 1 ))
if [[ "${clean_rows}" -ne "${enriched_rows}" ]]; then
    log_error "${STAGE}" "Row count mismatch after join: clean=${clean_rows}, enriched=${enriched_rows}"
    exit 4
fi

log_info "${STAGE}" "Aggregating deliveries by city, month, status, and vehicle with awk..."

AGG_CITY_CSV="${PROCESSED_DIR}/agg_par_ville.csv"
{
    echo "ville,total_deliveries,avg_poids,avg_distance,avg_temps,avg_speed_kmh,avg_cout,delay_rate_pct"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '
            {
                c = $4
                n[c]++
                w[c] += $6
                d[c] += $7
                t[c] += $8
                s[c] += $16
                cost[c] += $14
                if ($10 == "retarde") delayed[c]++
            }
            END {
                for (c in n) {
                    printf "%s,%d,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n",
                        c, n[c], w[c]/n[c], d[c]/n[c], t[c]/n[c], s[c]/n[c], cost[c]/n[c], (100.0 * delayed[c]) / n[c]
                }
            }
        ' \
        | sort -t',' -k2,2nr
} > "${AGG_CITY_CSV}"

AGG_MONTH_CSV="${PROCESSED_DIR}/agg_par_mois.csv"
{
    echo "year_month,total_deliveries,avg_temps,avg_cout,completed_count,delayed_count,cancelled_count"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '
            {
                m = $3
                n[m]++
                t[m] += $8
                cost[m] += $14
                if ($10 == "livre") comp[m]++
                if ($10 == "retarde") del[m]++
                if ($10 == "annule") canc[m]++
            }
            END {
                for (m in n) {
                    printf "%s,%d,%.2f,%.2f,%d,%d,%d\n", m, n[m], t[m]/n[m], cost[m]/n[m], comp[m]+0, del[m]+0, canc[m]+0
                }
            }
        ' \
        | sort -t',' -k1,1
} > "${AGG_MONTH_CSV}"

AGG_STATUS_CSV="${PROCESSED_DIR}/agg_par_statut.csv"
{
    echo "statut,total_deliveries,percentage"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '
            {
                total++
                cnt[$10]++
            }
            END {
                for (st in cnt) {
                    printf "%s,%d,%.2f\n", st, cnt[st], (100.0 * cnt[st]) / total
                }
            }
        ' \
        | sort -t',' -k2,2nr
} > "${AGG_STATUS_CSV}"

AGG_VEHICLE_CSV="${PROCESSED_DIR}/agg_par_vehicule.csv"
{
    echo "type_vehicule,total_deliveries,avg_poids,avg_distance,avg_temps,avg_speed_kmh,avg_cout,delay_rate_pct"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '
            {
                v = $13
                n[v]++
                w[v] += $6
                d[v] += $7
                t[v] += $8
                s[v] += $16
                cost[v] += $14
                if ($10 == "retarde") delayed[v]++
            }
            END {
                for (v in n) {
                    printf "%s,%d,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n",
                        v, n[v], w[v]/n[v], d[v]/n[v], t[v]/n[v], s[v]/n[v], cost[v]/n[v], (100.0 * delayed[v]) / n[v]
                }
            }
        ' \
        | sort -t',' -k2,2nr
} > "${AGG_VEHICLE_CSV}"

log_info "${STAGE}" "Converting city aggregation CSV to JSON using jq..."
AGG_CITY_JSON="${PROCESSED_DIR}/agg_par_ville.json"
tail -n +2 "${AGG_CITY_CSV}" \
    | jq -R -s '
        split("\n")
        | map(select(length > 0) | split(","))
        | map({
            ville: .[0],
            total_deliveries: (.[1] | tonumber),
            avg_poids: (.[2] | tonumber),
            avg_distance: (.[3] | tonumber),
            avg_temps: (.[4] | tonumber),
            avg_speed_kmh: (.[5] | tonumber),
            avg_cout: (.[6] | tonumber),
            delay_rate_pct: (.[7] | tonumber)
        })
    ' > "${AGG_CITY_JSON}"

log_info "${STAGE}" "Transformation pipeline completed (${enriched_rows} enriched rows)."
