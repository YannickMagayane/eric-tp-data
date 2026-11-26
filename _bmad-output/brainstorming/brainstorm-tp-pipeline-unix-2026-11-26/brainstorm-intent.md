# Synthese d'Intention — Projet Final Systemes UNIX & Integration Iragi

## 1. Vision Technique
Construire une plateforme reproductible d'analyse de donnees logistiques sous Docker combinant :
1. **La philosophie pure des pipelines UNIX** (`bash`, `sed`, `awk`, `sort`, `uniq`, `join`, `jq`, `gnuplot`) exigee par l'enonce academique.
2. **La rigueur d'audit de qualite de donnees avec `iragi` (`0.6.4`)** pour certifier les donnees avant et apres les filtres UNIX, appliquer des contrats metier (`DataContract`), isoler les rejets en Dead-Letter Queue (`auto_clean`) et reconcilier les journaux Apache avec les livraisons (`reconcile`).
3. **Une infrastructure propre et securisee** : `Dockerfile` multi-stage Debian + Python 3.14 non-root, `docker-compose.yml` orchestre derriere **Traefik** avec PostgreSQL et Metabase, points d'entree clairs dans `bin/` (`launch.sh`, `test.sh`, `backup.sh`) relies au `Makefile`, et developpement pilote par les tests (TDD).

## 2. Role Exact du Module `iragi` dans le TP
- **Profilage & Drift (`iragi.scan` + `iragi.compare_scans`)** : calcul du score de qualite explicable sur 100 sur `data/raw/livraisons.csv` puis sur `data/processed/livraisons_clean.csv` afin de prouver objectivement le gain apporte par `clean_data.sh`.
- **Contrats Metier & Quarantaine (`iragi.DataContract` + `iragi.auto_clean`)** : verification formelle des bornes de l'enonce (`poids` 5..50 kg, `distance` 10..500 km, `temps` 30..300 min, format ISO de `date`, valeurs autorisees de `statut`) et extraction des lignes invalides vers `data/processed/quarantine_livraisons.csv`.
- **Detection d'Anomalies (`detect_outliers_modified_zscore`)** : detection statistique robuste basee sur la mediane (MAD) en complement des seuils `awk`.
- **Reconciliation Inter-Sources (`iragi.reconcile`)** : rapprochement entre `livraisons.csv` (`id`) et les appels HTTP traces dans `access.log` (`/api/livraisons/LIV-<id>`) via `key_transform=r"(\d+)"`.

## 3. Architecture du Socle (Phase 1 + Acquisition Phase 2)
- `Dockerfile` : multi-stage sur base `python:3.14-slim-bookworm` (Debian), outils UNIX, `jq`, `gnuplot-nox`, `postgresql-client`, `shellcheck`, `iragi`, utilisateur non-root `appuser`.
- `docker-compose.yml` : services `traefik`, `db` (PostgreSQL 16 avec healthcheck), `dev` (conteneur UNIX/Python), `dashboard` (Metabase expose via Traefik).
- `bin/` : `bin/launch.sh`, `bin/test.sh`, `bin/backup.sh`.
- `scripts/etl/` : `validate_env.sh`, `generate_data.py` (donnees aleatoires conformes avec anomalies calibrees), `audit_quality.py` (audit `iragi`).
- `sql/` : `schema.sql` et `queries.sql`.
- `docs/` & `README.md` : documentation d'installation, d'architecture et squelette `docs/rapport.tex` synchronise avec les resultats.
