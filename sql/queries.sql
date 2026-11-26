-- Analytical SQL queries for Metabase dashboards and technical reporting

-- 1. Delivery volume, average duration, and delay rate per destination city
SELECT
    ville,
    COUNT(*) AS total_deliveries,
    ROUND(AVG(poids), 2) AS avg_weight_kg,
    ROUND(AVG(distance), 2) AS avg_distance_km,
    ROUND(AVG(temps), 2) AS avg_duration_min,
    ROUND(100.0 * SUM(CASE WHEN statut = 'retarde' THEN 1 ELSE 0 END) / COUNT(*), 2) AS delay_rate_pct
FROM deliveries
GROUP BY ville
ORDER BY total_deliveries DESC;

-- 2. Weekly delivery evolution over time
SELECT
    DATE_TRUNC('week', delivery_date)::DATE AS week_start,
    COUNT(*) AS deliveries_count,
    SUM(CASE WHEN statut = 'livre' THEN 1 ELSE 0 END) AS completed_count,
    SUM(CASE WHEN statut = 'annule' THEN 1 ELSE 0 END) AS cancelled_count
FROM deliveries
GROUP BY week_start
ORDER BY week_start;

-- 3. Courier fleet capacity and average rating by city and vehicle type
SELECT
    ville,
    vehicule,
    COUNT(*) AS couriers_count,
    ROUND(AVG(experience), 1) AS avg_experience_years,
    ROUND(AVG(note), 2) AS avg_rating
FROM couriers
GROUP BY ville, vehicule
ORDER BY ville, avg_rating DESC;

-- 4. HTTP error distribution from Apache access logs
SELECT
    http_status,
    COUNT(*) AS hits,
    ROUND(AVG(response_bytes), 0) AS avg_bytes
FROM web_access_logs
GROUP BY http_status
ORDER BY hits DESC;
