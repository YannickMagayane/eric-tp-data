#!/usr/bin/env bash
# Phase 3 & 4: Render 8 clean PNG charts via gnuplot with outside legends so nothing overlaps.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/etl/common.sh
source "${SCRIPT_DIR}/../etl/common.sh"

STAGE="VISUALIZE"
ensure_pipeline_dirs

REQUIRED_DATS=(
    "${PROCESSED_DIR}/par_ville.dat"
    "${PROCESSED_DIR}/par_mois.dat"
    "${PROCESSED_DIR}/dist_temps.dat"
    "${PROCESSED_DIR}/distance_vs_temps.dat"
    "${PROCESSED_DIR}/raw_distance_vs_temps.dat"
    "${PROCESSED_DIR}/par_statut.dat"
    "${PROCESSED_DIR}/perf_livreurs.dat"
    "${PROCESSED_DIR}/iragi_before_after.dat"
)

for dat_file in "${REQUIRED_DATS[@]}"; do
    if [[ ! -f "${dat_file}" ]]; then
        log_error "${STAGE}" "Missing gnuplot data file: ${dat_file}"
        exit 2
    fi
done

rm -f "${VISUALIZATIONS_DIR}"/*.png

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

log_info "${STAGE}" "Rendering 8 PNG charts into ${VISUALIZATIONS_DIR} with non-overlapping outside legends..."

read -r -d '' GP_COMMANDS << 'EOF' || true
data_dir = system("echo $DATA_MOUNT")
proc_dir = data_dir . "/processed"
vis_dir  = data_dir . "/visualizations"

# 1. Deliveries per city
set terminal png size 1240,700 noenhanced
set output vis_dir . "/01_livraisons_par_ville.png"
set title "Volume de livraisons par ville (Source: livraisons_clean.csv | Periode: Sept - Nov 2026)" offset 0,1.2
set tmargin 5.5
set bmargin 7.5
set lmargin 11
set rmargin 5
set style fill solid 0.85 border -1
set boxwidth 0.56
set grid ytics
set xlabel "Ville de destination (France)" offset 0,-1.2
set ylabel "Nombre de livraisons (colis)"
set yrange [0:*]
set offsets 0.5, 0.5, 35, 0
set xtics rotate by -25
set key outside top center horizontal
plot proc_dir . "/par_ville.dat" using 0:2:xtic(1) with boxes lc rgb "#1d4ed8" title "Livraisons validees", \
     "" using 0:2:(sprintf("%d", $2)) with labels offset 0,0.9 notitle

# 2. Monthly evolution of deliveries
reset
set terminal png size 1240,680 noenhanced
set output vis_dir . "/02_evolution_mensuelle.png"
set title "Evolution mensuelle des livraisons (Source: agg_par_mois.csv | Periode: Sept - Nov 2026)" offset 0,1.2
set tmargin 5.5
set bmargin 5.5
set lmargin 11
set rmargin 5
set style fill solid 0.85 border -1
set boxwidth 0.42
set grid ytics
set xlabel "Mois d'expedition (YYYY-MM)"
set ylabel "Volume mensuel (colis)"
set yrange [0:*]
set offsets 0.5, 0.5, 80, 0
set key outside top center horizontal
plot proc_dir . "/par_mois.dat" using 0:2:xtic(1) with boxes lc rgb "#0f766e" title "Total livraisons", \
     "" using 0:4 with linespoints lw 3 pt 7 ps 1.3 lc rgb "#dc2626" title "Livraisons retardees", \
     "" using 0:2:(sprintf("%d", $2)) with labels offset 0,0.9 notitle, \
     "" using 0:4:(sprintf("%d", $4)) with labels offset 0,1.1 tc rgb "#b91c1c" notitle

# 3. Delay rate per city
reset
set terminal png size 1240,700 noenhanced
set output vis_dir . "/03_taux_retard_par_ville.png"
set title "Taux de retard (%) par ville (Source: agg_par_ville.csv | Periode: Sept - Nov 2026)" offset 0,1.2
set tmargin 5.5
set bmargin 7.5
set lmargin 11
set rmargin 5
set style fill solid 0.85 border -1
set boxwidth 0.55
set grid ytics
set xlabel "Ville de destination (France)" offset 0,-1.2
set ylabel "Taux de retard (%)"
set yrange [0:20]
set xtics rotate by -25
set key outside top center horizontal
plot proc_dir . "/par_ville.dat" using 0:4:xtic(1) with boxes lc rgb "#dc2626" title "Taux de retard (%)", \
     "" using 0:4:(sprintf("%.1f%%", $4)) with labels offset 0,0.9 notitle

# 4. Delivery duration distribution
reset
set terminal png size 1240,680 noenhanced
set output vis_dir . "/04_distribution_temps.png"
set title "Distribution des temps de livraison (Source: livraisons_enriched.csv | Periode: Sept - Nov 2026)" offset 0,1.2
set tmargin 5.5
set bmargin 5.5
set lmargin 11
set rmargin 5
set xlabel "Tranche de duree (minutes)"
set ylabel "Nombre de livraisons (colis)"
set style fill solid 0.85 border -1
set boxwidth 0.65
set grid ytics
set yrange [0:*]
set offsets 0.4, 0.4, 45, 0
set key outside top center horizontal
plot proc_dir . "/dist_temps.dat" using 0:3:xtic(1) with boxes lc rgb "#4338ca" title "Effectif par tranche de 30 min", \
     "" using 0:3:(sprintf("%.1f%%", $4)) with labels offset 0,0.9 notitle

# 5. Distance vs delivery duration
reset
set terminal png size 1240,680 noenhanced
set output vis_dir . "/05_distance_vs_temps.png"
set title "Relation Distance vs Temps de livraison (Source: livraisons_enriched.csv | Sept - Nov 2026)" offset 0,1.2
set tmargin 5.5
set bmargin 5.5
set lmargin 11
set rmargin 5
set xlabel "Distance parcourue (km)"
set ylabel "Temps de livraison (minutes)"
set xrange [0:525]
set yrange [0:325]
set grid
set fit quiet
set fit logfile "/dev/null"
f(x) = a*x + b
fit f(x) proc_dir . "/distance_vs_temps.dat" using 1:2 via a,b
set key outside top center horizontal
plot proc_dir . "/distance_vs_temps.dat" using 1:2 with points pt 7 ps 0.45 lc rgb "#64748b" title "Livraisons valides", \
     f(x) with lines lw 3 lc rgb "#e11d48" title sprintf("Tendance lineaire : Temps = %.3f * Dist + %.1f", a, b)

# 6. Status breakdown
reset
set terminal png size 1200,660 noenhanced
set output vis_dir . "/06_repartition_statuts.png"
set title "Repartition des statuts de livraison (Source: agg_par_statut.csv | Periode: Sept - Nov 2026)" offset 0,1.2
set tmargin 5.5
set bmargin 5.5
set lmargin 11
set rmargin 5
set style fill solid 0.85 border -1
set boxwidth 0.48
set grid ytics
set xlabel "Statut de livraison"
set ylabel "Pourcentage des livraisons (%)"
set yrange [0:85]
set key outside top center horizontal
plot proc_dir . "/par_statut.dat" using 0:3:xtic(1) with boxes lc rgb "#0284c7" title "Part du trafic (%)", \
     "" using 0:3:(sprintf("%.1f%% (%d)", $3, $2)) with labels offset 0,0.9 notitle

# 7. Courier performance (Experience vs Rating)
reset
set terminal png size 1240,660 noenhanced
set output vis_dir . "/07_performance_livreurs.png"
set title "Performance des livreurs : Note moyenne vs Experience (Source: livreurs_clean.csv | Sept - Nov 2026)" offset 0,1.2
set tmargin 5.5
set bmargin 5.5
set lmargin 11
set rmargin 5
set xlabel "Experience du livreur (annees)"
set ylabel "Note moyenne (/5)"
set yrange [2.0:5.4]
set xrange [-1:31]
set grid
set key outside top center horizontal
plot proc_dir . "/perf_livreurs.dat" using 3:4 with points pt 7 ps 1.5 lc rgb "#d97706" title "Livreurs actifs (n=35)"

# 8. Anomalies before vs after treatment (Raw vs Classical Naive vs UNIX + Iragi)
reset
set terminal png size 1320,720 noenhanced
set output vis_dir . "/08_anomalies_avant_apres.png"
set title "Comparaison des anomalies : Brut vs Nettoyage Classique vs Pipeline UNIX + Iragi (Sept - Nov 2026)" offset 0,1.6
set tmargin 7.0
set bmargin 6.0
set lmargin 11
set rmargin 5
set style data histograms
set style histogram cluster gap 1.4
set style fill solid 0.88 border -1
set boxwidth 0.9
set xlabel "Categorie d'anomalie / risque qualite"
set ylabel "Nombre d'anomalies detectees"
set grid ytics
set yrange [0:*]
set offsets 0, 0, 18, 0
set key outside top center vertical
plot proc_dir . "/iragi_before_after.dat" using 2:xtic(1) lc rgb "#dc2626" title "1. Donnees brutes (data/raw)", \
     "" using 3 lc rgb "#f59e0b" title "2. Nettoyage classique naif (sans DataContract/DLQ)", \
     "" using 4 lc rgb "#16a34a" title "3. Pipeline UNIX + Iragi (0 violation, DLQ + Reconcile)", \
     "" using ($0 - 0.25):2:(sprintf("%d", $2)) with labels offset 0,0.8 tc rgb "#991b1b" notitle, \
     "" using ($0):3:(sprintf("%d", $3)) with labels offset 0,0.8 tc rgb "#b45309" notitle, \
     "" using ($0 + 0.25):4:(sprintf("%d", $4)) with labels offset 0,0.8 tc rgb "#15803d" notitle

# 9. Side-by-Side Data Impact: BEFORE Iragi (Raw with outliers) vs AFTER UNIX + Iragi Contract
reset
set terminal png size 1440,720 noenhanced
set output vis_dir . "/09_impact_donnees_avant_apres_iragi.png"
set multiplot layout 1,2 title "Impact reel sur les donnees : AVANT Iragi (Brut) vs APRES Pipeline UNIX + Contrat Iragi (Sept - Nov 2026)"

set tmargin 5.0
set bmargin 7.5
set lmargin 10
set rmargin 3
set title "AVANT Iragi : Donnees brutes avec hors-contrats (>500km / >300min)" offset 0,0.6
set xlabel "Distance (km)" offset 0,0.4
set ylabel "Temps de livraison (minutes)"
set xrange [0:900]
set yrange [0:540]
set grid
set key outside bottom center horizontal
set arrow 1 from 500,0 to 500,540 nohead dt 2 lw 2 lc rgb "#dc2626"
set arrow 2 from 0,300 to 900,300 nohead dt 2 lw 2 lc rgb "#dc2626"
plot proc_dir . "/raw_distance_vs_temps.dat" using 1:2 with points pt 7 ps 0.55 lc rgb "#dc2626" title "Brut (incl. hors-contrats 820km/490min)"

unset arrow 1
unset arrow 2
set tmargin 5.0
set bmargin 7.5
set title "APRES UNIX + Iragi : 2510 livraisons conformes (DLQ isolee)" offset 0,0.6
set xlabel "Distance (km) [Contrat : 10..500 km]" offset 0,0.4
set ylabel "Temps (minutes) [Contrat : 30..300 min]"
set xrange [0:530]
set yrange [0:330]
set grid
set fit quiet
set fit logfile "/dev/null"
g(x) = m*x + c
fit g(x) proc_dir . "/distance_vs_temps.dat" using 1:2 via m,c
set key outside bottom center horizontal
plot proc_dir . "/distance_vs_temps.dat" using 1:2 with points pt 7 ps 0.50 lc rgb "#0f766e" title "Certifiees (0 violation)", \
     g(x) with lines lw 3 lc rgb "#1d4ed8" title sprintf("Tendance (r=0.9296)")

unset multiplot
EOF

run_gnuplot_script "${GP_COMMANDS}" "${DATA_DIR}"
log_info "${STAGE}" "All 9 PNG charts successfully generated in ${VISUALIZATIONS_DIR}."
