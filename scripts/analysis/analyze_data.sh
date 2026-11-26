#!/usr/bin/env bash
# Phase 2 - Task 4: UNIX statistical analysis, distributions, correlations, anomalies, and gnuplot feeds.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/../etl/common.sh"

STAGE="ANALYZE"
ensure_pipeline_dirs

ENRICHED_CSV="${PROCESSED_DIR}/livraisons_enriched.csv"
CLEAN_COURIERS="${PROCESSED_DIR}/livreurs_clean.csv"
CLEAN_LOGS="${PROCESSED_DIR}/access_clean.csv"
REJECTED_CSV="${PROCESSED_DIR}/livraisons_rejected_unix.csv"
AGG_CITY_CSV="${PROCESSED_DIR}/agg_par_ville.csv"

for req in "${ENRICHED_CSV}" "${CLEAN_COURIERS}" "${CLEAN_LOGS}" "${AGG_CITY_CSV}"; do
    if [[ ! -f "${req}" ]]; then
        log_error "${STAGE}" "Missing required input for analysis: ${req}"
        exit 2
    fi
done

log_info "${STAGE}" "Computing descriptive statistics (mean, median, min, max, stddev)..."
STATS_CSV="${REPORTS_DIR}/stats_descriptives.csv"
echo "metric,count,mean,median,min,max,stddev" > "${STATS_CSV}"

compute_column_stats() {
    local metric_name="$1"
    local col_idx="$2"
    tail -n +2 "${ENRICHED_CSV}" \
        | cut -d',' -f"${col_idx}" \
        | sort -n \
        | awk -v metric="${metric_name}" '
            {
                n++
                vals[n] = $1 + 0.0
                sum += vals[n]
                sum_sq += vals[n] * vals[n]
            }
            END {
                if (n == 0) exit 1
                mean = sum / n
                if (n % 2 == 1) {
                    median = vals[(n + 1) / 2]
                } else {
                    median = (vals[n / 2] + vals[(n / 2) + 1]) / 2.0
                }
                variance = (sum_sq / n) - (mean * mean)
                if (variance < 0) variance = 0
                stddev = sqrt(variance)
                printf "%s,%d,%.2f,%.2f,%.2f,%.2f,%.2f\n",
                    metric, n, mean, median, vals[1], vals[n], stddev
            }
        ' >> "${STATS_CSV}"
}

compute_column_stats "poids" 5
compute_column_stats "distance" 6
compute_column_stats "temps" 7
compute_column_stats "speed_kmh" 9

log_info "${STAGE}" "Generating delivery duration histogram with awk..."
HIST_REPORT="${REPORTS_DIR}/hist_temps.dat"
DIST_GNUPLOT="${PROCESSED_DIR}/dist_temps.dat"

tail -n +2 "${ENRICHED_CSV}" \
    | awk -F',' '
        {
            t = $7 + 0
            bin = int(t / 30) * 30
            if (bin >= 300) bin = 270
            bins[bin]++
            total++
        }
        END {
            printf "# bin_range\tbin_mid\tcount\tpercentage\thistogram\n"
            for (b = 30; b <= 270; b += 30) {
                hi = (b == 270) ? 300 : (b + 29)
                c = bins[b] + 0
                pct = (total > 0) ? (100.0 * c / total) : 0.0
                bars = ""
                bar_len = int(pct / 2)
                for (i = 0; i < bar_len; i++) bars = bars "#"
                printf "%d-%d\t%d\t%d\t%.2f\t%s\n", b, hi, b + 15, c, pct, bars
            }
        }
    ' > "${HIST_REPORT}"

cp "${HIST_REPORT}" "${DIST_GNUPLOT}"

log_info "${STAGE}" "Calculating Pearson correlations in awk..."
CORR_CSV="${REPORTS_DIR}/correlations.csv"
echo "pair,pearson_r,sample_size" > "${CORR_CSV}"

compute_pearson() {
    local label="$1"
    local col_x="$2"
    local col_y="$3"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' -v pair="${label}" -v cx="${col_x}" -v cy="${col_y}" '
            {
                x = $cx + 0.0
                y = $cy + 0.0
                n++
                sx += x; sy += y
                sxx += x * x; syy += y * y
                sxy += x * y
            }
            END {
                num = (n * sxy) - (sx * sy)
                den_x = (n * sxx) - (sx * sx)
                den_y = (n * syy) - (sy * sy)
                den = sqrt(den_x * den_y)
                r = (den > 0) ? (num / den) : 0.0
                printf "%s,%.4f,%d\n", pair, r, n
            }
        ' >> "${CORR_CSV}"
}

compute_pearson "distance_vs_temps" 6 7
compute_pearson "poids_vs_temps" 5 7
compute_pearson "distance_vs_speed_kmh" 6 9

log_info "${STAGE}" "Detecting operational anomalies across deliveries and HTTP logs..."
ANOMALIES_CSV="${REPORTS_DIR}/anomalies.csv"
{
    echo "source,record_ref,anomaly_type,detail"
    if [[ -f "${REJECTED_CSV}" ]]; then
        tail -n +2 "${REJECTED_CSV}" \
            | awk -F',' '{ printf "livraisons_raw,%s,%s,%s\n", ($1 != "" ? $1 : "MISSING_ID"), $8, $3 }'
    fi
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '
            ($9 + 0.0) > 150.0 || ($9 + 0.0) < 15.0 {
                printf "delivery_speed,%s,extreme_speed_kmh,%.2f\n", $1, $9
            }
        '
    tail -n +2 "${CLEAN_LOGS}" \
        | awk -F',' '
            ($5 + 0) >= 400 {
                printf "access_log,%s,http_error_%d,%s\n", $4, $5, $1
            }
        '
} > "${ANOMALIES_CSV}"

log_info "${STAGE}" "Generating gnuplot-ready .dat files..."
{
    printf "# ville\ttotal_deliveries\tavg_temps\tdelay_rate_pct\n"
    tail -n +2 "${AGG_CITY_CSV}" \
        | awk -F',' '{ printf "%s\t%d\t%.2f\t%.2f\n", $1, $2, $5, $7 }'
} > "${PROCESSED_DIR}/par_ville.dat"

{
    printf "# date\tdeliveries_count\n"
    tail -n +2 "${ENRICHED_CSV}" \
        | cut -d',' -f2 \
        | sort \
        | uniq -c \
        | awk '{ printf "%s\t%d\n", $2, $1 }'
} > "${PROCESSED_DIR}/par_date.dat"

{
    printf "# distance\ttemps\tstatut\n"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '{ printf "%d\t%d\t%s\n", $6, $7, $8 }'
} > "${PROCESSED_DIR}/distance_vs_temps.dat"

{
    printf "# courier_id\tville\texperience\tnote\tvehicule\n"
    tail -n +2 "${CLEAN_COURIERS}" \
        | awk -F',' '{ printf "%d\t%s\t%d\t%.2f\t%s\n", $1, $3, $4, $5, $6 }'
} > "${PROCESSED_DIR}/perf_livreurs.dat"

anomaly_count=$(( $(wc -l < "${ANOMALIES_CSV}") - 1 ))
log_info "${STAGE}" "Analysis completed (${anomaly_count} total anomaly records catalogued)."
