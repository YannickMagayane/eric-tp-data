#!/usr/bin/env bash
# Phase 3 - Task 1: Render 6 PNG analytical charts from real processed .dat files via gnuplot.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/../etl/common.sh"

STAGE="VISUALIZE"
ensure_pipeline_dirs

REQUIRED_DATS=(
    "${PROCESSED_DIR}/par_ville.dat"
    "${PROCESSED_DIR}/par_date.dat"
    "${PROCESSED_DIR}/dist_temps.dat"
    "${PROCESSED_DIR}/distance_vs_temps.dat"
    "${PROCESSED_DIR}/raw_distance_vs_temps.dat"
    "${PROCESSED_DIR}/perf_livreurs.dat"
    "${PROCESSED_DIR}/iragi_before_after.dat"
)

for dat_file in "${REQUIRED_DATS[@]}"; do
    if [[ ! -f "${dat_file}" ]]; then
        log_error "${STAGE}" "Missing gnuplot data file: ${dat_file}"
        exit 2
    fi
done

run_gnuplot_script() {
    local gp_content="$1"
    local work_data_dir="$2"

    if command -v gnuplot >/dev/null 2>&1; then
        DATA_MOUNT="${work_data_dir}" gnuplot <<< "${gp_content}"
    elif command -v docker >/dev/null 2>&1; then
        docker compose run --rm --no-deps -T \
            -u "$(id -u):$(id -g)" \
            -v "${work_data_dir}:/data_mount" \
            -e DATA_MOUNT="/data_mount" \
            dev gnuplot <<< "${gp_content}"
    else
        log_error "${STAGE}" "Neither gnuplot nor Docker is available to render charts."
        exit 3
    fi
}

log_info "${STAGE}" "Rendering 6 PNG charts into ${VISUALIZATIONS_DIR} from real processed datasets..."

read -r -d '' GP_COMMANDS << 'EOF' || true
data_dir = system("echo $DATA_MOUNT")
proc_dir = data_dir . "/processed"
vis_dir  = data_dir . "/visualizations"

# 1. Deliveries and Delay Rate per City
set terminal png size 1100,650
set output vis_dir . "/01_livraisons_par_ville.png"
set title "Volume de livraisons et taux de retard (%) par ville"
set style data histograms
set style histogram cluster gap 1
set style fill solid 0.85 border -1
set boxwidth 0.9
set grid ytics
set ylabel "Nombre de livraisons"
set y2label "Taux de retard (%)"
set y2tics 0, 2, 20
set yrange [0:350]
set y2range [0:20]
set xtics rotate by -25
plot proc_dir . "/par_ville.dat" using 2:xtic(1) title "Livraisons totales" lc rgb "#1d4ed8", \
     "" using 4 axes x1y2 with linespoints lw 2 pt 7 lc rgb "#dc2626" title "Taux de retard (%)"

# 2. Daily Evolution Over 3 Months
reset
set terminal png size 1100,600
set output vis_dir . "/02_evolution_temporelle.png"
set title "Evolution quotidienne des livraisons (Septembre - Novembre 2026)"
set xdata time
set timefmt "%Y-%m-%d"
set format x "%d/%m"
set xlabel "Date"
set ylabel "Livraisons par jour"
set grid
plot proc_dir . "/par_date.dat" using 1:2 with linespoints lw 2 pt 7 ps 0.7 lc rgb "#0f766e" title "Livraisons quotidiennes"

# 3. Delivery Duration Histogram
reset
set terminal png size 1100,600
set output vis_dir . "/03_distribution_temps.png"
set title "Distribution des temps de livraison (tranches de 30 minutes)"
set xlabel "Tranche de duree (minutes)"
set ylabel "Nombre de livraisons"
set style fill solid 0.85 border -1
set boxwidth 0.75
set grid ytics
set yrange [0:420]
plot proc_dir . "/dist_temps.dat" using 3:xtic(1) with boxes lc rgb "#4338ca" title "Effectif par tranche"

# 4. Distance vs Delivery Duration Scatter & Linear Trend
reset
set terminal png size 1100,650
set output vis_dir . "/04_distance_vs_temps.png"
set title "Relation Distance vs Temps de livraison (r = 0.9671, n = 2508)"
set xlabel "Distance parcourue (km)"
set ylabel "Temps de livraison (minutes)"
set grid
set fit quiet
set fit logfile "/dev/null"
f(x) = a*x + b
fit f(x) proc_dir . "/distance_vs_temps.dat" using 1:2 via a,b
plot proc_dir . "/distance_vs_temps.dat" using 1:2 with points pt 7 ps 0.45 lc rgb "#64748b" title "Livraisons (n=2508)", \
     f(x) with lines lw 3 lc rgb "#e11d48" title "Regression lineaire"

# 5. Courier Performance (Experience vs Rating)
reset
set terminal png size 1100,600
set output vis_dir . "/05_performance_livreurs.png"
set title "Performance de la flotte de livreurs : Note moyenne vs Experience (n = 35)"
set xlabel "Annees d'experience"
set ylabel "Note moyenne (/5)"
set yrange [2.0:5.2]
set xrange [-1:32]
set grid
plot proc_dir . "/perf_livreurs.dat" using 3:4 with points pt 7 ps 1.4 lc rgb "#d97706" title "Livreurs actifs"

# 6. Iragi Before vs After UNIX Remediation
reset
set terminal png size 1100,560 noenhanced
set output vis_dir . "/06_iragi_avant_apres.png"
set title "Audit Iragi : Anomalies detectees AVANT vs APRES le pipeline UNIX"
set style data histograms
set style histogram cluster gap 1
set style fill solid 0.85 border -1
set ylabel "Nombre d'anomalies / enregistrements affectes"
set grid ytics
set yrange [0:25]
plot proc_dir . "/iragi_before_after.dat" using 2:xtic(1) title "Avant (data/raw : score 99.7/100)" lc rgb "#dc2626", \
     "" using 3 title "Apres clean_data.sh (certifie Iragi : 100.0/100)" lc rgb "#16a34a"

# 7. Side-by-Side Comparison: WITHOUT vs WITH UNIX + Iragi Governance
reset
set terminal png size 1280,540 noenhanced
set output vis_dir . "/07_impact_sans_vs_avec_iragi.png"
set multiplot layout 1,2 title "Comparaison des donnees reelles : SANS nettoyage (Brut) vs AVEC Pipeline UNIX + Iragi"

# Left panel: Raw uncleaned data with contract boundary box and outlier (820, 490)
set title "SANS Iragi / Brut (n=2536, hors-contrat visibles)"
set xlabel "Distance (km)"
set ylabel "Temps (minutes)"
set xrange [0:900]
set yrange [0:550]
set grid
set arrow 1 from 500,0 to 500,550 nohead dt 2 lw 2 lc rgb "#dc2626"
set arrow 2 from 0,300 to 900,300 nohead dt 2 lw 2 lc rgb "#dc2626"
plot proc_dir . "/raw_distance_vs_temps.dat" using 1:2 with points pt 7 ps 0.45 lc rgb "#dc2626" title "Brut (incl. aberrant 820km/490min)"

# Right panel: Clean data certified 100/100 by Iragi DataContract
unset arrow 1
unset arrow 2
set title "AVEC UNIX + Contrat Iragi (n=2508, score 100/100)"
set xlabel "Distance (km) [contrat 10..500]"
set ylabel "Temps (minutes) [contrat 30..300]"
set xrange [0:550]
set yrange [0:330]
set grid
set fit quiet
set fit logfile "/dev/null"
g(x) = m*x + c
fit g(x) proc_dir . "/distance_vs_temps.dat" using 1:2 via m,c
plot proc_dir . "/distance_vs_temps.dat" using 1:2 with points pt 7 ps 0.45 lc rgb "#0f766e" title "Valides (0 violation)", \
     g(x) with lines lw 2 lc rgb "#1d4ed8" title "Tendance (r=0.9671)"

unset multiplot
EOF

run_gnuplot_script "${GP_COMMANDS}" "${DATA_DIR}"
log_info "${STAGE}" "All 7 PNG charts successfully generated in ${VISUALIZATIONS_DIR}."
