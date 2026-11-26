#!/usr/bin/env bash
# Phase 2 - Task 4: UNIX statistical analysis (mean, median, quartiles, IQR, distributions, Pearson r, anomalies, .dat feeds).

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
AGG_MONTH_CSV="${PROCESSED_DIR}/agg_par_mois.csv"
AGG_STATUS_CSV="${PROCESSED_DIR}/agg_par_statut.csv"

for req in "${ENRICHED_CSV}" "${CLEAN_COURIERS}" "${CLEAN_LOGS}" "${AGG_CITY_CSV}" "${AGG_MONTH_CSV}" "${AGG_STATUS_CSV}"; do
    if [[ ! -f "${req}" ]]; then
        log_error "${STAGE}" "Missing required input for analysis: ${req}"
        exit 2
    fi
done

log_info "${STAGE}" "Computing descriptive statistics including quartiles (Q1, median, Q3, IQR)..."
STATS_CSV="${REPORTS_DIR}/stats_descriptives.csv"
echo "metric,count,mean,median,q1,q3,iqr,min,max,stddev" > "${STATS_CSV}"

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
                median = (n % 2 == 1) ? vals[(n + 1) / 2] : (vals[n / 2] + vals[(n / 2) + 1]) / 2.0
                q1_idx = int(n * 0.25); if (q1_idx < 1) q1_idx = 1
                q3_idx = int(n * 0.75); if (q3_idx < 1) q3_idx = 1
                q1 = vals[q1_idx]
                q3 = vals[q3_idx]
                iqr = q3 - q1
                variance = (sum_sq / n) - (mean * mean)
                if (variance < 0) variance = 0
                stddev = sqrt(variance)
                printf "%s,%d,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\n",
                    metric, n, mean, median, q1, q3, iqr, vals[1], vals[n], stddev
            }
        ' >> "${STATS_CSV}"
}

compute_column_stats "poids" 6
compute_column_stats "distance" 7
compute_column_stats "temps" 8
compute_column_stats "temps_prevu" 9
compute_column_stats "cout_livraison" 14
compute_column_stats "speed_kmh" 16

log_info "${STAGE}" "Generating duration and distance distributions with awk..."
HIST_TEMPS="${REPORTS_DIR}/hist_temps.dat"
DIST_GNUPLOT="${PROCESSED_DIR}/dist_temps.dat"

tail -n +2 "${ENRICHED_CSV}" \
    | awk -F',' '
        {
            t = $8 + 0
            bin = int(t / 30) * 30
            if (bin >= 300) bin = 270
            bins[bin]++
            total++
        }
        END {
            printf "# bin_range\tbin_mid\tcount\tpercentage\n"
            for (b = 30; b <= 270; b += 30) {
                hi = (b == 270) ? 300 : (b + 29)
                c = bins[b] + 0
                pct = (total > 0) ? (100.0 * c / total) : 0.0
                printf "%d-%d\t%d\t%d\t%.2f\n", b, hi, b + 15, c, pct
            }
        }
    ' > "${HIST_TEMPS}"
cp "${HIST_TEMPS}" "${DIST_GNUPLOT}"

HIST_DIST="${REPORTS_DIR}/hist_distance.dat"
tail -n +2 "${ENRICHED_CSV}" \
    | awk -F',' '
        {
            d = $7 + 0
            bin = int(d / 50) * 50
            if (bin >= 500) bin = 450
            bins[bin]++
            total++
        }
        END {
            printf "# bin_range\tcount\tpercentage\n"
            for (b = 0; b <= 450; b += 50) {
                hi = (b == 450) ? 500 : (b + 49)
                lo = (b == 0) ? 10 : b
                c = bins[b] + 0
                pct = (total > 0) ? (100.0 * c / total) : 0.0
                printf "%d-%d\t%d\t%.2f\n", lo, hi, c, pct
            }
        }
    ' > "${HIST_DIST}"

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
                x = $cx + 0.0; y = $cy + 0.0
                n++; sx += x; sy += y
                sxx += x * x; syy += y * y; sxy += x * y
            }
            END {
                num = (n * sxy) - (sx * sy)
                den = sqrt(((n * sxx) - (sx * sx)) * ((n * syy) - (sy * sy)))
                r = (den > 0) ? (num / den) : 0.0
                printf "%s,%.4f,%d\n", pair, r, n
            }
        ' >> "${CORR_CSV}"
}

compute_pearson "distance_vs_temps" 7 8
compute_pearson "poids_vs_temps" 6 8
compute_pearson "distance_vs_cout" 7 14

log_info "${STAGE}" "Detecting operational anomalies across deliveries and HTTP logs..."
ANOMALIES_CSV="${REPORTS_DIR}/anomalies.csv"
{
    echo "source,record_ref,anomaly_type,detail"
    if [[ -f "${REJECTED_CSV}" ]]; then
        tail -n +2 "${REJECTED_CSV}" \
            | awk -F',' '{ printf "livraisons_raw,%s,%s,%s\n", ($1 != "" ? $1 : "MISSING_ID"), $15, $3 }'
    fi
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '
            ($17 + 0) > 60 {
                printf "delivery_delay,%s,high_delay_minutes,+%dmin\n", $1, $17
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
    printf "# ville\ttotal_deliveries\tavg_temps\tdelay_rate_pct\tavg_cout\n"
    tail -n +2 "${AGG_CITY_CSV}" \
        | awk -F',' '{ printf "%s\t%d\t%.2f\t%.2f\t%.2f\n", $1, $2, $5, $8, $7 }'
} > "${PROCESSED_DIR}/par_ville.dat"

{
    printf "# year_month\ttotal_deliveries\tavg_temps\tdelayed_count\n"
    tail -n +2 "${AGG_MONTH_CSV}" \
        | awk -F',' '{ printf "%s\t%d\t%.2f\t%d\n", $1, $2, $3, $6 }'
} > "${PROCESSED_DIR}/par_mois.dat"

{
    printf "# statut\ttotal_deliveries\tpercentage\n"
    tail -n +2 "${AGG_STATUS_CSV}" \
        | awk -F',' '{ printf "%s\t%d\t%.2f\n", $1, $2, $3 }'
} > "${PROCESSED_DIR}/par_statut.dat"

{
    printf "# distance\ttemps\tstatut\n"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '{ if (NR <= 5000 || NR % 25 == 0) printf "%d\t%d\t%s\n", $7, $8, $10 }'
} > "${PROCESSED_DIR}/distance_vs_temps.dat"

{
    printf "# courier_id\tville\texperience\tnote\tvehicule\tdeliveries_handled\n"
    tail -n +2 "${ENRICHED_CSV}" \
        | awk -F',' '{ handled[$5]++ } END {
            while ((getline line < "'"${CLEAN_COURIERS}"'") > 0) {
                if (line ~ /^id,/) continue
                split(line, f, ",")
                printf "%d\t%s\t%d\t%.2f\t%s\t%d\n", f[1], f[3], f[4], f[5], f[6], handled[f[1]] + 0
            }
        }'
} > "${PROCESSED_DIR}/perf_livreurs.dat"

anomaly_count=$(( $(wc -l < "${ANOMALIES_CSV}") - 1 ))
log_info "${STAGE}" "Analysis completed (${anomaly_count} total anomaly records catalogued)."
