# Guide d'Installation, de Deploiement et d'Utilisation

**Projet Final — Systemes UNIX (M1 Informatique, Universite de Lubumbashi)**  
**Etudiant** : Lutumba Miteo Eric | **Enseignant** : Prof. Patrick Mukala

---

## 1. Prerequis Systeme

- **Docker Engine** (`v20.10+`) et **Docker Compose** (`v2.0+`)
- **GNU Make**, **Bash** (`v5.0+`), `sed`, `gawk`, `jq`, `curl`
- **TeX Live (`pdflatex` + `beamer`)** pour recompiler le rapport et les slides
- Au moins **5 Go** d'espace disque disponible

---

## 2. Architecture et Flux des Donnees

La plateforme traite les flux logistiques sur les **9 grandes villes francaises** (**Paris, Lyon, Marseille, Lille, Bordeaux, Toulouse, Nantes, Nice, Strasbourg**) avec **Traefik v3.2** comme reverse proxy unique devant **Metabase**, et **PostgreSQL 16** pour le stockage relationnel.

1. **`data/raw/`** : donnees brutes (`livraisons.csv`, `livreurs.json`, `access.log`) + `generation_manifest.json`.
2. **`data/processed/`** : sorties UNIX nettoyees (`livraisons_clean.csv`, `livreurs_clean.csv`, `access_clean.csv`), rejets (`livraisons_rejected_unix.csv`), quarantaine `iragi` (`quarantine_livraisons.csv`), donnees enrichies (`livraisons_enriched.csv`), agregations et fichiers `.dat`.
3. **`data/reports/`** : audits JSON (`iragi_audit.json`, `pipeline_status.json`, `lineage_manifest.json`), statistiques (`stats_descriptives.csv`, `correlations.csv`), `anomalies.csv`, `pipeline.log` et rapports `latest_report.md` / `dashboard_report.html`.
4. **`data/visualizations/`** : 8 graphiques PNG generes par `gnuplot`.

---

## 3. Commandes Docker Essentielles

```bash
# Construire les images
docker compose build

# Demarrer tous les services (traefik, db, dev, dashboard)
docker compose up -d

# Verifier les healthchecks
docker compose ps

# Suivre les logs
docker compose logs -f

# Entrer dans le conteneur UNIX dev (non-root appuser)
docker compose exec dev bash

# Redemarrer / arreter sans supprimer les volumes
docker compose restart
docker compose down
```

---

## 4. Execution Complete Pas-a-Pas

```bash
# 1. Demarrer la stack Docker
./bin/launch.sh

# 2. Generer les donnees (MODE=exam par defaut, ou MODE=extended pour 12k/ville/mois)
make generate-data MODE=exam
# ou : make generate-data MODE=extended

# 3. Executer le pipeline UNIX + audit iragi + tracabilite SHA-256
make pipeline

# 4. Generer les 8 graphiques gnuplot, rapports HTML/MD, rapport PDF et slides PDF
make charts
make report
make pdf
make slides

# 5. Charger PostgreSQL et connecter Metabase (http://metabase.localhost:8080)
make load-db

# 6. Lancer les tests d'integration bout-en-bout + shellcheck
./bin/test.sh

# 7. Sauvegarder les donnees et la base PostgreSQL (avec verification SHA-256)
./bin/backup.sh
```

**Parametres de connexion Metabase -> PostgreSQL :**
- **Host** : `db` | **Port** : `5432` | **Database** : `logistics_db` | **User** : `logistics` | **Password** : `logistics_pass`
