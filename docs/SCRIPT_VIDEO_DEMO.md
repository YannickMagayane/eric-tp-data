# Script de Demonstration & Presentation Video (OBS Studio - 12 min)

**Etudiant** : Lutumba Miteo Eric | **Cours** : Systemes UNIX (M1 Informatique)  
**Resolution recommandee** : 1920x1080 (1080p) sous OBS Studio.

---

## 1. Introduction (1 min 30)
- Presentation personnelle : *Lutumba Miteo Eric, M1 Informatique, Universite de Lubumbashi*.
- Contexte : Analyse de donnees logistiques sur 9 villes francaises (`livraisons.csv`, `livreurs.json`, `access.log`) avec exigence de reproductibilite Docker et gouvernance qualite `iragi`.

## 2. Architecture du Systeme (2 min 30)
- Afficher `README.md` et `docker-compose.yml` :
  - **Traefik v3.6** (reverse proxy unique sur `:8080`)
  - **Conteneur `dev`** (image multi-stage Debian / Python 3.14, utilisateur non-root `appuser` UID 1000)
  - **PostgreSQL 16 (`db`)** + **Metabase (`dashboard`)**
- Lancer dans le terminal :
  ```bash
  docker compose ps
  ```
  Montrer les 4 services en statut `healthy`.

## 3. Demonstration en Direct (4 min 30)
- **Etape 1 — Generation EXAM & Pipeline UNIX + Audit `iragi`** :
  ```bash
  make generate-data MODE=exam
  make pipeline
  ```
  Commenter les logs horodates (`clean_data.sh`, `transform_data.sh`, `analyze_data.sh`, `audit_quality.py`, `lineage_manifest.json`).
- **Etape 2 — Graphiques & Rapports** :
  ```bash
  make charts && make report
  ```
  Ouvrir `data/visualizations/08_anomalies_avant_apres.png` et `data/reports/dashboard_report.html`.
- **Etape 3 — PostgreSQL & Metabase** :
  ```bash
  make load-db
  ```
  Ouvrir `http://metabase.localhost:8080` dans le navigateur et montrer le tableau de bord **"Analyse Logistique - Pipeline UNIX"** connecte a PostgreSQL.

## 4. Resultats, Analyses & Validation TDD (2 min 30)
- Presenter les tableaux et graphiques dans `docs/rapport.pdf` et `docs/slides.pdf` :
  - Score `iragi` passant de `99.29` a `99.75/100` (`0` violation restante, `10` lignes en quarantaine DLQ, `139` appels HTTP `404` orphelins identifies).
  - Correlation distance/temps ($r = 0.9296$), performance par ville (Paris `377` colis, Strasbourg `6.75 %` de retard).
- Lancer la suite de tests :
  ```bash
  ./bin/test.sh
  ```
  Montrer les `17/17` tests passes + `shellcheck` a `0` alerte.

## 5. Conclusion & Montee en Charge (1 min 30)
- Mentionner la validation du mode `MODE=extended` (`329 410` livraisons en 21 s avec `iragi.scan_csv_stream`) et la sauvegarde SHA-256 (`./bin/backup.sh`).
- Publier la video sur YouTube (Non repertoriee ou Publique) et coller l'URL dans `docs/rapport.tex`, puis relancer `make pdf`.
