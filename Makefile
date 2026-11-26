# Makefile delegating operational tasks to standardized scripts in bin/ and scripts/

.PHONY: help launch test validate generate generate-data pipeline charts report pdf slides load-db audit backup down update-tree

PYTHON ?= docker compose exec -T dev python3
MODE ?= exam
MONTHS ?= 3
PER_CITY_MONTH ?= 12000
SEED ?= 2026

help:
	@echo "Available targets:"
	@echo "  make launch                       - Build and launch Docker + Traefik + PostgreSQL + Metabase stack"
	@echo "  make validate                     - Validate UNIX tools, volume mounts, and database connectivity"
	@echo "  make generate-data MODE=exam      - Generate EXAM compliant dataset (default)"
	@echo "  make generate-data MODE=extended  - Generate EXTENDED volume dataset (12k/city/month)"
	@echo "  make pipeline                     - Run full UNIX ETL + analysis + Iragi before/after audit"
	@echo "  make charts                       - Render all 8 gnuplot PNG visualizations from real data"
	@echo "  make report                       - Generate timestamped Markdown and TailwindCSS HTML reports"
	@echo "  make pdf                          - Compile docs/rapport.tex into docs/rapport.pdf"
	@echo "  make slides                       - Compile docs/slides.tex into docs/slides.pdf"
	@echo "  make load-db                      - Load cleaned CSV tables into PostgreSQL for Metabase"
	@echo "  make audit                        - Run Iragi data quality scan, DataContract DLQ, and reconciliation"
	@echo "  make test                         - Execute isolated pytest suite and shellcheck"
	@echo "  make backup                       - Create SHA-256 verified archive of datasets and PostgreSQL"
	@echo "  make down                         - Stop running Docker services"

launch:
	./bin/launch.sh

validate:
	./scripts/etl/validate_env.sh

generate: generate-data

generate-data:
	$(PYTHON) -m scripts.etl.generate_data --mode $(MODE) --months $(MONTHS) --per-city-month $(PER_CITY_MONTH) --seed $(SEED)

pipeline:
	./scripts/etl/run_pipeline.sh

charts:
	./scripts/reporting/generate_charts.sh

report:
	./scripts/reporting/generate_report.sh

pdf:
	cd docs && pdflatex -interaction=nonstopmode rapport.tex >/dev/null && pdflatex -interaction=nonstopmode rapport.tex >/dev/null && rm -f rapport.aux rapport.log rapport.toc rapport.out

slides:
	cd docs && pdflatex -interaction=nonstopmode slides.tex >/dev/null && pdflatex -interaction=nonstopmode slides.tex >/dev/null && rm -f slides.aux slides.log slides.nav slides.out slides.snm slides.toc

load-db:
	./scripts/etl/load_postgres.sh

audit:
	$(PYTHON) -m scripts.etl.audit_quality

test:
	./bin/test.sh

backup:
	./bin/backup.sh

update-tree:
	$(PYTHON) -m scripts.reporting.update_readme_tree

down:
	docker compose down
