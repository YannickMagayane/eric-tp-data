#!/usr/bin/env bash
# Phase 2 - Task 3: UNIX transformation pipeline using awk, sort, join, and jq.

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

log_info "${STAGE}" "Computing courier metrics per city and joining with deliveries via UNIX join..."

TMP_CITY_COURIERS="${PROCESSED_DIR}/.tmp_city_couriers.csv"
TMP_DERIVED_DELIVERIES="${PROCESSED_DIR}/.tmp_derived_deliveries.csv"
TMP_JOINED="${PROCESSED_DIR}/.tmp_joined_deliveries.csv"
ENRICHED_CSV="${PROCESSED_DIR}/livraisons_enriched.csv"

tail -n +2 "${CLEAN_COURIERS}" \
    | awk -F',' '
        {
            city = $3
            cnt[city]++
            rating_sum[city] += $5
        }
        END {
            for (c in cnt) {
                printf "%s,%d,%.2f\n", c, cnt[c], rating_sum[c] / cnt[c]
            }
        }
    ' \
    | sort -t',' -k1,1 > "${TMP_CITY_COURIERS}"

# Derive speed_kmh and year_month with awk, then sort on column 3 (ville) for UNIX join
tail -n +2 "${CLEAN_DELIVERIES}" \
    | awk -F',' '
        BEGIN { OFS = "," }
        {
            speed = ($5 * 60.0) / $6
            ym = substr($2, 1, 7)
            printf "%s,%s,%s,%s,%s,%s,%s,%.2f,%s\n", $1, $2, $3, $4, $5, $6, $7, speed, ym
        }
    ' \
    | sort -t',' -k3,3 > "${TMP_DERIVED_DELIVERIES}"

join -t',' -a 1 -e '0' -1 3 -2 1 \
    -o 1.1,1.2,1.9,1.3,1.4,1.5,1.6,1.7,1.8,2.2,2.3 \
    "${TMP_DERIVED_DELIVERIES}" "${TMP_CITY_COURIERS}" \
    | sort -t',' -k1,1n > "${TMP_JOINED}"

{
    echo "id,date,year_month,ville,poids,distance,temps,statut,speed_kmh,city_couriers_count,city_avg_rating"
    cat "${TMP_JOINED}"
} > "${ENRICHED_CSV}"

rm -f "${TMP_CITY_COURIERS}" "${TMP_DERIVED_DELIVERIES}" "${TMP_JOINED}"

log_info "${STAGE}" "Aggregating deliveries by city, month, and status with awk..."

AGG_CITY_CSV="${PROCESSED_DIR}/agg_par_ville.csv"
{
    echo "ville,total_deliveries,avg_poids,avg_distance,avg_temps,avg_speed_kmh,delay_rate_pct"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '
            {
                c = $4
                n[c]++
                w[c] += $5
                d[c] += $6
                t[c] += $7
                s[c] += $9
                if ($8 == "retarde") delayed[c]++
            }
            END {
                for (c in n) {
                    printf "%s,%d,%.2f,%.2f,%.2f,%.2f,%.2f\n",
                        c, n[c], w[c]/n[c], d[c]/n[c], t[c]/n[c], s[c]/n[c], (100.0 * delayed[c]) / n[c]
                }
            }
        ' \
        | sort -t',' -k2,2nr
} > "${AGG_CITY_CSV}"

AGG_MONTH_CSV="${PROCESSED_DIR}/agg_par_mois.csv"
{
    echo "year_month,total_deliveries,avg_temps,completed_count,delayed_count,cancelled_count"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '
            {
                m = $3
                n[m]++
                t[m] += $7
                if ($8 == "livre") comp[m]++
                if ($8 == "retarde") del[m]++
                if ($8 == "annule") canc[m]++
            }
            END {
                for (m in n) {
                    printf "%s,%d,%.2f,%d,%d,%d\n", m, n[m], t[m]/n[m], comp[m]+0, del[m]+0, canc[m]+0
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
                cnt[$8]++
            }
            END {
                for (st in cnt) {
                    printf "%s,%d,%.2f\n", st, cnt[st], (100.0 * cnt[st]) / total
                }
            }
        ' \
        | sort -t',' -k2,2nr
} > "${AGG_STATUS_CSV}"

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
            delay_rate_pct: (.[6] | tonumber)
        })
    ' > "${AGG_CITY_JSON}"

log_info "${STAGE}" "Transformation pipeline completed."
