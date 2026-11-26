-- PostgreSQL schema for the UNIX Logistics Data Pipeline

CREATE TABLE IF NOT EXISTS couriers (
    id INTEGER PRIMARY KEY,
    nom VARCHAR(120) NOT NULL,
    ville VARCHAR(64) NOT NULL,
    experience INTEGER NOT NULL CHECK (experience BETWEEN 0 AND 30),
    note NUMERIC(3, 2) NOT NULL CHECK (note BETWEEN 0 AND 5),
    vehicule VARCHAR(32) NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY,
    delivery_date DATE NOT NULL,
    ville VARCHAR(64) NOT NULL,
    poids NUMERIC(6, 2) NOT NULL CHECK (poids BETWEEN 5 AND 50),
    distance INTEGER NOT NULL CHECK (distance BETWEEN 10 AND 500),
    temps INTEGER NOT NULL CHECK (temps BETWEEN 30 AND 300),
    statut VARCHAR(24) NOT NULL CHECK (statut IN ('livre', 'en_cours', 'retarde', 'annule')),
    speed_kmh NUMERIC(6, 2)
);

CREATE TABLE IF NOT EXISTS web_access_logs (
    log_id SERIAL PRIMARY KEY,
    client_ip VARCHAR(45) NOT NULL,
    logged_at VARCHAR(64) NOT NULL,
    http_method VARCHAR(12) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    http_status INTEGER NOT NULL,
    response_bytes INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deliveries_ville ON deliveries(ville);
CREATE INDEX IF NOT EXISTS idx_deliveries_date ON deliveries(delivery_date);
CREATE INDEX IF NOT EXISTS idx_deliveries_statut ON deliveries(statut);
