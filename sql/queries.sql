-- Analytical SQL queries for Metabase dashboards and technical reporting

-- 1. Delivery volume, delay rate, average distance, duration, and cost per city
SELECT
    ville,
    COUNT(*) AS total_deliveries,
    ROUND(AVG(distance), 2) AS avg_distance_km,
    ROUND(AVG(temps), 2) AS avg_duration_min,
    ROUND(AVG(cout_livraison), 2) AS avg_cost_eur,
    ROUND(100.0 * SUM(CASE WHEN statut = 'retarde' THEN 1 ELSE 0 END) / COUNT(*), 2) AS delay_rate_pct
FROM deliveries
GROUP BY ville
ORDER BY total_deliveries DESC;

-- 2. Monthly delivery evolution over time
SELECT
    DATE_TRUNC('month', delivery_date)::DATE AS month_start,
    COUNT(*) AS deliveries_count,
    SUM(CASE WHEN statut = 'livre' THEN 1 ELSE 0 END) AS completed_count,
    SUM(CASE WHEN statut = 'retarde' THEN 1 ELSE 0 END) AS delayed_count,
    SUM(CASE WHEN statut = 'annule' THEN 1 ELSE 0 END) AS cancelled_count
FROM deliveries
GROUP BY month_start
ORDER BY month_start;

-- 3. Status distribution
SELECT
    statut,
    COUNT(*) AS total_deliveries,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM deliveries
GROUP BY statut
ORDER BY total_deliveries DESC;

-- 4. Vehicle type comparison
SELECT
    type_vehicule,
    COUNT(*) AS deliveries_count,
    ROUND(AVG(poids), 2) AS avg_weight_kg,
    ROUND(AVG(distance), 2) AS avg_distance_km,
    ROUND(AVG(temps), 2) AS avg_duration_min,
    ROUND(AVG(speed_kmh), 2) AS avg_speed_kmh,
    ROUND(AVG(cout_livraison), 2) AS avg_cost_eur
FROM deliveries
GROUP BY type_vehicule
ORDER BY deliveries_count DESC;

-- 5. Courier performance joined with deliveries
SELECT
    c.id AS courier_id,
    c.nom,
    c.ville,
    c.vehicule,
    c.experience,
    c.note,
    COUNT(d.id) AS deliveries_handled,
    ROUND(AVG(d.temps), 2) AS avg_delivery_min
FROM couriers c
LEFT JOIN deliveries d ON d.livreur_id = c.id
GROUP BY c.id, c.nom, c.ville, c.vehicule, c.experience, c.note
ORDER BY deliveries_handled DESC, c.note DESC;

-- 6. HTTP status anomalies from Apache access logs
SELECT
    http_status,
    http_method,
    COUNT(*) AS hits,
    ROUND(AVG(response_bytes), 0) AS avg_bytes
FROM web_access_logs
GROUP BY http_status, http_method
ORDER BY hits DESC;
