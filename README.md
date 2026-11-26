# Analyse de Donnees avec Pipeline UNIX

**Projet Final — Systemes UNIX (Master 1 Informatique, Universite de Lubumbashi)**  
**Etudiant** : Lutumba Miteo Eric | **Enseignant** : Prof. Patrick Mukala

---

## 1. Presentation du Projet

Ce projet met en oeuvre une plateforme complete et reproductible de traitement, d'audit de qualite, de stockage relationnel et de visualisation de donnees logistiques. Il repose sur l'alliance entre les **pipelines UNIX natifs** (`bash`, `sed`, `awk`, `sort`, `uniq`, `cut`, `join`, `jq`, `gnuplot`), une **infrastructure conteneurisee Docker + Traefik + PostgreSQL 16 + Metabase**, et le toolkit Python **`iragi`** (`v0.6.4`) pour la gouvernance formelle de la qualite des donnees.

## 2. Problematique

Une entreprise de logistique opere sur neuf grandes villes francaises (**Paris, Lyon, Marseille, Lille, Bordeaux, Toulouse, Nantes, Nice, Strasbourg**) et collecte quotidiennement trois flux heterogenes (`livraisons.csv`, `livreurs.json`, `access.log`). Sans chaine d'ingestion fiable, les analyses sont faussees par des doublons, des lignes vides, des valeurs hors-contrat et des erreurs HTTP non correlees.

## 3. Objectifs

- Deployer un environnement reproductible et isole sous Docker avec utilisateur non-root (`appuser`, UID 1000) et reverse proxy **Traefik**.
- Respecter strictement le cahier des charges de l'examen en mode **EXAM** tout en offrant un mode **EXTENDED** pour tester la montee en charge (12 000 livraisons/mois/ville).
- Orchestrer des pipelines UNIX modulaires, deterministes (`LC_ALL=C`, `set -euo pipefail`) et traces de bout en bout.
- Garantir la qualite metier et la reconciliation inter-sources via **`iragi`**.
- Alimenter **PostgreSQL 16** et **Metabase**, generer 8 graphiques **`gnuplot`** et compiler un rapport universitaire LaTeX/PDF.

## 4. Fonctionnalites

- Generation synthetique realiste en deux modes (`MODE=exam` et `MODE=extended`).
- Nettoyage, enrichissement, jointure UNIX `join`, agregations multi-axes et calcul de statistiques (moyenne, mediane, quartiles Q1/Q3, IQR, ecart-type, correlations de Pearson).
- Audit 3 voies `iragi` (Brut vs Approche Classique Naive vs Pipeline UNIX + `iragi`), quarantaine *Dead-Letter Queue* (`quarantine_livraisons.csv`) et reconciliation logs HTTP / livraisons.
- Chargement transactionnel PostgreSQL, dashboard Metabase derriere Traefik, rapports Markdown/HTML horodates, 8 graphiques PNG, tests TDD (`pytest`) et analyse statique (`shellcheck`).

## 5. Architecture Globale

```text
                       +-----------------------------+
                       |     Traefik v3.2 (:8080)    |
                       |   Unique Reverse Proxy      |
                       +--------------+--------------+
                                      | Host: metabase.localhost
                                      v
+--------------------+     +----------+-----------+     +-----------------------+
| data/raw/          |---->| Conteneur dev        |---->| PostgreSQL 16 (db)    |
| - livraisons.csv   |     | Debian + Python 3.14 |     | - couriers            |
| - livreurs.json    |     | - Filtres UNIX       |     | - deliveries          |
| - access.log       |     | - iragi 0.6.4        |     | - web_access_logs     |
+--------------------+     | - gnuplot / jq       |     +-----------+-----------+
                           +----------+-----------+                 |
                                      |                             |
                                      v                             v
                           +----------+-----------+     +-----------+-----------+
                           | data/processed/      |     | Metabase (dashboard)  |
                           | data/reports/        |     | Visualisation BI      |
                           | data/visualizations/ |     +-----------------------+
                           +----------------------+
```

## 6. Technologies Utilisees

| Composant | Technologie | Role |
| :--- | :--- | :--- |
| Conteneurisation | Docker & Docker Compose v2+ | Isolation multi-services et reproductibilite |
| Reverse Proxy | Traefik v3.6 | Routage HTTP unique vers Metabase |
| Traitement ETL | Bash, sed, gawk, sort, uniq, cut, join, jq | Nettoyage, jointure et agregation en flux |
| Qualite & Audit | Python 3.14 + `iragi` (`0.6.4`) | Scan, `DataContract`, DLQ, `reconcile` |
| Base de donnees | PostgreSQL 16 (Alpine) | Stockage relationnel et requetes SQL |
| BI & Graphiques | Metabase + `gnuplot-nox` | Dashboards interactifs et 8 PNG |
| Qualite & Docs | `pytest`, `shellcheck`, LaTeX (`pdflatex`) | Tests TDD, lint shell et rapport PDF |

## 7. Prerequis

- **Docker Engine** (`v20.10+`) et **Docker Compose** (`v2.0+`)
- **GNU Make**, **Bash** (`v5.0+`), `jq`, `curl`
- **TeX Live** (`pdflatex`, `beamer`) pour recompiler `docs/rapport.pdf` et `docs/slides.pdf`
- **5 Go** d'espace disque disponible

## 8. Installation

```bash
# Cloner le depot du projet et entrer dans le dossier
git clone <URL_DU_DEPOT_GIT>
cd eric

# Construire et demarrer toute la stack Docker (Traefik, PostgreSQL, Metabase, dev)
./bin/launch.sh
```

## 9. Configuration

Les services Docker utilisent des valeurs par defaut coherentes dans `docker-compose.yml` (surchargeables par variables d'environnement) :
- `TRAEFIK_HTTP_PORT` : `8080` (point d'entree HTTP Traefik)
- `TRAEFIK_DASHBOARD_PORT` : `8081` (interface d'administration Traefik)
- `POSTGRES_USER` : `logistics` | `POSTGRES_DB` : `logistics_db` | `PGPORT` : `5432`
- `MODE` (`Makefile`) : `exam` (par defaut) ou `extended`

## 10. Structure des Repertoires

```text
.
├── Dockerfile                          # Image multi-stage Debian + Python 3.14 non-root (appuser)
├── docker-compose.yml                  # Services traefik, db, dev, dashboard + healthchecks
├── Makefile                            # Commandes unifiees (generate-data, pipeline, charts, etc.)
├── requirements.txt                    # Dependances Python installees dans l'image Docker (iragi, pytest)
├── README.md                           # Documentation technique principale
├── bin/
│   ├── launch.sh                       # Construction, demarrage Docker et validation runtime
│   ├── test.sh                         # Execution isolee pytest + shellcheck
│   └── backup.sh                       # Sauvegarde pg_dump + tar.gz verifiee par SHA-256
├── backups/                            # Dumps SQL PostgreSQL et archives .tar.gz + empreintes .sha256
├── data/
│   ├── raw/                            # Donnees brutes (CSV, JSON, access.log) + generation_manifest.json
│   ├── processed/                      # Donnees nettoyees, enrichies, DLQ et fichiers .dat
│   ├── reports/                        # Audits JSON, stats, anomalies, lineage_manifest.json, MD/HTML
│   └── visualizations/                 # 10 graphiques PNG generes par gnuplot (01 a 10)
├── scripts/
│   ├── etl/                            # common.sh, validate_env.sh, generate_data.py, clean/transform/run/load, audit_quality.py
│   ├── analysis/                       # analyze_data.sh (stats, quartiles, Pearson r, .dat)
│   └── reporting/                      # generate_charts.sh, generate_report.sh, render_report.py, setup_metabase.py
├── sql/
│   ├── schema.sql                      # Schema PostgreSQL (couriers, deliveries, web_access_logs, iragi_audit_metrics)
│   └── queries.sql                     # Requetes SQL analytiques pour Metabase
├── docs/
│   ├── GUIDE_INSTALLATION_UTILISATION.md
│   ├── SCRIPT_VIDEO_DEMO.md            # Trame de presentation pour la video YouTube
│   ├── rapport.tex / rapport.pdf       # Rapport universitaire LaTeX et PDF compile
│   └── slides.tex / slides.pdf         # Presentation Beamer PDF (10 diapositives)
└── tests/                              # Suites TDD (foundation, phase2, phase3, phase4_e2e)
```

## 11. Organisation des Donnees et Tracabilite

1. **Entree brute (`data/raw/`)** : `livraisons.csv` (14 colonnes), `livreurs.json` (7 champs) et `access.log` (Apache), accompagnes de `generation_manifest.json`.
2. **Nettoyage (`data/processed/livraisons_clean.csv`)** : produit par `clean_data.sh` apres suppression des lignes vides, normalisation d'espaces (`sed`), deduplication (`sort | uniq`) et filtrage contractuel (`awk`).
3. **Gestion des rejets et quarantaine DLQ** :
   - Rejets UNIX traces dans `data/processed/livraisons_rejected_unix.csv` avec motif exact (`reason`).
   - Quarantaine metier `iragi` isolee dans `data/processed/quarantine_livraisons.csv`.
4. **Enrichissement et agregations (`data/processed/`)** : `livraisons_enriched.csv` (jointure UNIX `join` avec `livreurs_clean.csv`), `agg_par_ville.csv/.json`, `agg_par_mois.csv`, `agg_par_statut.csv`, `agg_par_vehicule.csv` et fichiers `.dat` pour `gnuplot`.
5. **Resultats analytiques et tracabilite (`data/reports/`)** : `stats_descriptives.csv`, `correlations.csv`, `anomalies.csv`, `iragi_audit.json`, `pipeline_status.json`, `pipeline.log` et `lineage_manifest.json` (empreintes SHA-256 a chaque etape).
6. **Chargement PostgreSQL & Metabase** : `scripts/etl/load_postgres.sh` peuple les tables `couriers`, `deliveries` et `web_access_logs` dans `db`, interrogees directement par Metabase.

## 12. Generation des Donnees (Modes EXAM et EXTENDED)

Les donnees sont **synthetiques** (les coefficients de variation simules ne constituent pas des statistiques officielles).

```bash
# Mode A : EXAM (par defaut - conforme au cahier des charges : 1000-5000 livraisons, 9 villes FR, 3 mois)
make generate-data MODE=exam

# Mode B : EXTENDED (montee en charge : 12 000 livraisons/mois/ville = ~324 000 sur 3 mois)
make generate-data MODE=extended

# Personnalisation des parametres en mode EXTENDED :
make generate-data MODE=extended MONTHS=3 PER_CITY_MONTH=12000 SEED=2026
```

## 13. Lancement et Gestion de Docker (Commandes Exactes)

```bash
# Construire les images Docker (multi-stage dev)
docker compose build

# Demarrer tous les services en arriere-plan (traefik, db, dev, dashboard)
docker compose up -d

# Verifier l'etat et les healthchecks des conteneurs
docker compose ps

# Consulter les journaux en temps reel
docker compose logs -f

# Ouvrir un shell interactif dans le conteneur de developpement (utilisateur non-root appuser)
docker compose exec dev bash

# Redemarrer les services
docker compose restart

# Arreter les services en preservant les volumes (pgdata, metabase_data)
docker compose down

# Supprimer les conteneurs tout en preservant explicitement les volumes (ne pas ajouter -v)
docker compose rm -s -f
```

Ou en une seule commande automatisee (build + demarrage + validation runtime) :
```bash
./bin/launch.sh
```

**URLs et ports d'acces reels :**
- **Metabase (via Traefik)** : `http://metabase.localhost:8080` (ou avec en-tete `Host: metabase.localhost` sur `http://127.0.0.1:8080`)
- **Dashboard Traefik** : `http://127.0.0.1:8081`
- **PostgreSQL (reseau interne Docker `pipeline_net`)** : hote `db`, port `5432`, base `logistics_db`

## 14. Execution des Pipelines

```bash
# Valider les outils UNIX et les permissions
make validate

# Executer la chaine complete : clean -> transform -> analyze -> audit iragi -> lineage SHA-256
make pipeline
```

Chaque script peut aussi etre execute independamment (`./scripts/etl/clean_data.sh`, `./scripts/etl/transform_data.sh`, `./scripts/analysis/analyze_data.sh`).

## 15. Chargement PostgreSQL

```bash
make load-db
```

## 16. Connexion Metabase

1. Ouvrir `http://metabase.localhost:8080` dans votre navigateur.
2. Ajouter une source de donnees **PostgreSQL** avec les parametres internes au reseau Docker :
   - **Host** : `db`
   - **Port** : `5432`
   - **Database name** : `logistics_db`
   - **Username** : `logistics`
   - **Password** : `logistics_pass`

## 17. Consultation du Dashboard

- **Metabase** : exploitez les tables `deliveries`, `couriers` et `web_access_logs` et les 6 requetes pretes dans `sql/queries.sql` (volume/retard par ville, evolution mensuelle, statuts, vehicules, performance livreurs, anomalies HTTP).
- **Dashboard HTML statique** : ouvrez `data/reports/dashboard_report.html`.

## 18. Utilisation d'`iragi`

`iragi` (`v0.6.4`) complete les filtres UNIX sans les remplacer :
- **Inspection (`iragi.scan` / `iragi.scan_csv_stream`)** : calcule un score de qualite explicable sur 100 avant et apres nettoyage (streaming automatique au-dela de 50 000 lignes en mode `extended`).
- **Contrat metier (`iragi.DataContract`, `validate_contract`)** : verifie les bornes et formats reglementaires (villes francaises, dates ISO, poids 5..50 kg, distance 10..500 km, temps/temps prevu 30..300 min, statuts).
- **Quarantaine DLQ (`iragi.auto_clean(..., contract_action="quarantine")`)** : isole les lignes invalides dans `data/processed/quarantine_livraisons.csv` sans imputation aveugle.
- **Outliers (`detect_outliers_modified_zscore`)** : detection robuste basee sur la mediane (MAD).
- **Reconciliation (`iragi.reconcile`)** : rapprochement par regex `r"(\d+)"` entre `livraisons.csv` et `access.log`.

**Limites d'`iragi`** : `auto_clean` et `validate_contract` chargent un DataFrame Pandas en memoire ; pour des flux massifs (> 50 000 lignes), le filtrage initial reste plus rapide et sobre en memoire avec `awk`/`sed`/`sort` en flux, tandis qu'`iragi.scan_csv_stream` assure le profilage borne.

## 19. Execution des Tests

```bash
# Suite complete : tests unitaires, pipelines UNIX, graphiques, PDF, E2E Docker/PostgreSQL/Metabase + shellcheck
./bin/test.sh
```

## 20. Generation des Graphiques et Rapports

```bash
make charts   # Genere les 8 PNG dans data/visualizations/
make report   # Genere data/reports/latest_report.md et dashboard_report.html
make pdf      # Compile docs/rapport.pdf
make slides   # Compile docs/slides.pdf
```

## 21. Sauvegarde

```bash
./bin/backup.sh
```
Exporte un dump SQL `pg_dump` de PostgreSQL, archive `data/` et `sql/` dans `backups/logistics_backup_<horodatage>.tar.gz` et verifie l'integrite via `sha256sum`.

## 22. Depannage

- **Metabase met du temps a repondre** : le premier demarrage JVM prend ~45-60s ; suivez l'etat avec `docker compose ps` et `docker compose logs -f dashboard`.
- **`metabase.localhost` non resolu par le navigateur** : ajoutez `127.0.0.1 metabase.localhost` dans `/etc/hosts` ou testez avec `curl -H "Host: metabase.localhost" http://127.0.0.1:8080/api/health`.
- **Conflit de port 8080** : lancez avec `TRAEFIK_HTTP_PORT=8090 docker compose up -d`.

## 23. Limites du Projet

- Les jeux de donnees sont synthetiques (regles metier simulees pour reproduire des distributions plausibles).
- Le tableau de bord Metabase est deja provisionne automatiquement (`http://metabase.localhost:8080/dashboard/2`, compte `eric.lutumba@unilu.ac.cd` / `UnixPipeline2026!`) ; seule l'activation d'un lien de partage public ou l'export PDF dans l'interface web reste a la main de l'utilisateur.

## 24. Perspectives d'Evolution

- Planification automatique des pipelines UNIX via `cron` ou un ordonnanceur (Airflow / Dagster) pour une execution quotidienne.
- Integration continue (CI/CD) executant automatiquement `shellcheck`, `./bin/test.sh` et la compilation LaTeX a chaque mise a jour du depot.

## 25. Conclusion et Bilan de l'Apport d'`iragi`

Ce projet demontre la synergie entre une infrastructure UNIX/Docker robuste et une gouvernance rigoureuse de la qualite des donnees. Tandis que les scripts UNIX (`sed`, `awk`, `sort`, `uniq`, `join`, `jq`) assurent le traitement rapide des fichiers texte, **`iragi` (`0.6.4`)** a joue le role de controleur qualite et de certificateur dans `scripts/etl/audit_quality.py` sur cinq points precis :

1. **Mesure objective de la qualite (`iragi.scan` + `iragi.compare_scans`)** : attribution d'un score chiffre aux donnees brutes (`99.29 / 100`), puis certification de la sortie de `clean_data.sh` a `99.75 / 100` (`+0.46 pt`, aucune cellule manquante).
2. **Application d'un contrat metier strict (`iragi.DataContract`)** : controle automatise des 9 villes francaises, des dates ISO, des bornes physiques (`poids`, `distance`, `temps`) et des statuts, confirmant **0 violation restante** apres le pipeline UNIX.
3. **Quarantaine DLQ sans corruption statistique (`iragi.auto_clean`)** : au lieu d'imputer aveuglement les champs vides par une moyenne, isolement des **10 lignes fautives** dans `data/processed/quarantine_livraisons.csv` avec parite exacte (`2 510 == 2 510` lignes).
4. **Detection robuste d'outliers temporels (`detect_outliers_modified_zscore`)** : reperage des temps anormaux via le Z-score modifie base sur la mediane (MAD), adapte aux distributions asymetriques.
5. **Reconciliation inter-sources (`iragi.reconcile`)** : liaison par regex `key_transform=r"(\d+)"` entre `id` (CSV) et `/api/livraisons/LIV-<id>` (`access.log`), permettant de retrouver **751 livraisons suivies sur le web** et de decouvrir **139 appels HTTP 404 orphelins**.
