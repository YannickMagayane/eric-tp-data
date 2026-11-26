# Analyse de Donnees Logistiques avec Pipeline UNIX et Iragi

Projet Final — Systemes UNIX (M1 Informatique, Universite de Lubumbashi).

Ce depot met en oeuvre une infrastructure reproductible sous Docker (orchestration via **Traefik**, **PostgreSQL 16**, **Metabase**, et conteneur de traitement **Debian / Python 3.14 non-root**) combinant les pipelines UNIX classiques (`bash`, `sed`, `awk`, `sort`, `uniq`, `jq`, `gnuplot`) et la bibliotheque Python **`iragi`** (`0.6.4`) pour l'inspection de qualite, les contrats de donnees (`DataContract`), la mise en quarantaine (*Dead-Letter Queue*) et la reconciliation inter-sources.

## Architecture du Systeme

```text
                       +------------------------+
                       |   Traefik v3 (:8080)   |
                       | Reverse Proxy Unique   |
                       +-----------+------------+
                                   |
                        Host: metabase.localhost
                                   v
+--------------------+    +--------+---------+    +---------------------+
| Data Lake Local    |--->| Conteneur dev    |--->| PostgreSQL 16 (db)  |
| data/raw/          |    | - Filtres UNIX   |    | - couriers          |
| - livraisons.csv   |    | - Python 3.14    |    | - deliveries        |
| - livreurs.json    |    | - iragi 0.6.4    |    | - web_access_logs   |
| - access.log       |    | - gnuplot / jq   |    +----------+----------+
+--------------------+    +------------------+               |
                                   |                         |
                                   v                         v
                       +------------------------+  +--------------------+
                       | data/processed/ &      |  | Metabase Dashboard |
                       | data/reports/ &        |  | Visualisation BI   |
                       | data/visualizations/   |  +--------------------+
                       +------------------------+
```

## Structure du Projet

```text
.
├── Dockerfile                  # Image multi-stage Debian + Python 3.14 non-root (appuser)
├── docker-compose.yml          # Services traefik, db, dev, dashboard + healthchecks
├── Makefile                    # Interface unifiee deleguant aux scripts de bin/
├── bin/
│   ├── launch.sh               # Demarrage et validation de la stack Docker
│   ├── test.sh                 # Execution isolee des tests pytest et shellcheck
│   └── backup.sh               # Sauvegarde horodatee data/ + PostgreSQL avec SHA-256
├── data/
│   ├── raw/                    # Jeux de donnees bruts generes (CSV, JSON, logs Apache)
│   ├── processed/              # Donnees nettoyees et quarantaine DLQ (quarantine_livraisons.csv)
│   ├── reports/                # Rapports d'audit JSON (iragi_audit.json) et rapports HTML/MD
│   └── visualizations/         # Graphiques generes avec gnuplot
├── scripts/
│   ├── etl/
│   │   ├── common.sh           # Fonctions partagees de journalisation et gestion des chemins
│   │   ├── validate_env.sh     # Verification des outils UNIX, permissions et PostgreSQL
│   │   ├── generate_data.py    # Generateur aleatoire reproductible avec anomalies calibrees
│   │   ├── clean_data.sh       # Nettoyage UNIX (sed, sort | uniq, awk, jq) -> 100/100 Iragi
│   │   ├── transform_data.sh   # Colonnes derivees, jointure UNIX join, agregations awk et jq
│   │   ├── load_postgres.sh    # Chargement transactionnel PostgreSQL pour Metabase
│   │   ├── run_pipeline.sh     # Orchestrateur complet avec trap d'erreurs et statut JSON
│   │   └── audit_quality.py    # Audit Iragi AVANT (data/raw) et APRES (clean_data.sh) + DLQ
│   ├── analysis/
│   │   └── analyze_data.sh     # Stats descriptives, histogramme awk, Pearson r, anomalies, .dat
│   └── reporting/
│       ├── generate_charts.sh  # Generation des 6 graphiques PNG via gnuplot sur donnees reelles
│       ├── generate_report.sh  # Generation horodatee des rapports Markdown et HTML TailwindCSS
│       └── render_report.py    # Moteur de synthese dynamique sans aucune valeur codee en dur
├── sql/
│   ├── schema.sql              # Schema relationnel PostgreSQL avec contraintes CHECK
│   └── queries.sql             # Requetes analytiques pour Metabase et reporting
├── docs/
│   ├── rapport.tex             # Source LaTeX complete avec tableaux reels et figures gnuplot
│   └── rapport.pdf             # Rapport technique compile au format PDF
└── tests/
    ├── test_foundation.py      # Suite de tests TDD du socle, des donnees et d'iragi
    ├── test_phase2_pipelines.py # Suite de tests TDD isolee des pipelines UNIX Phase 2
    └── test_phase3_reporting.py # Suite de tests TDD Phase 3 (Avant/Apres Iragi, gnuplot, PDF)
```

## Role du Module `iragi` en Complement des Pipelines UNIX

Les pipelines principaux de nettoyage et de transformation utilisent strictement les filtres UNIX demandes par le cours (`sed`, `awk`, `sort`, `uniq`, `join`, `jq`). Le paquet `iragi` (`pip install iragi`) agit comme **couche d'audit formel et de gouvernance des donnees** :

1. **Score de qualite avant/apres (`iragi.scan` & `iragi.compare_scans`)** : mesure objective sur 100 de la qualite de `data/raw/livraisons.csv` puis du gain net (`score_delta`) apres nettoyage.
2. **Contrat metier et Quarantaine DLQ (`iragi.DataContract` & `iragi.auto_clean`)** : controle des regles exactes du cahier des charges (`poids` entre 5 et 50 kg, `distance` entre 10 et 500 km, `temps` entre 30 et 300 min, format ISO de `date`, valeurs de `statut`) et isolation automatique des lignes corrompues dans `data/processed/quarantine_livraisons.csv`.
3. **Detection robuste d'anomalies (`detect_outliers_modified_zscore`)** : reperage des temps de livraison atypiques par Z-Score modifie (base sur la mediane MAD).
4. **Reconciliation inter-sources (`iragi.reconcile`)** : croisement entre `livraisons.csv` (`id` numerique) et les appels HTTP extraits de `access.log` (`/api/livraisons/LIV-<id>`) via `key_transform=r"(\d+)"` afin d'identifier les requetes orphelines (`404`).

## Demarrage Rapide

### 1. Generer les donnees et executer tout le pipeline UNIX + Iragi

```bash
make generate
make pipeline
```

### 2. Executer les tests et la validation d'environnement

```bash
./bin/test.sh
./scripts/etl/validate_env.sh
```

### 3. Lancer l'environnement complet Docker + Traefik

```bash
./bin/launch.sh
```

### 4. Sauvegarder les donnees critiques

```bash
./bin/backup.sh
```
