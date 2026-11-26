# Makefile delegating operational tasks to standardized scripts in bin/ and scripts/

.PHONY: help launch test validate generate pipeline audit backup down

PYTHON ?= $(shell if [ -x .venv/bin/python3 ]; then echo .venv/bin/python3; else echo python3; fi)

help:
	@echo "Available targets:"
	@echo "  make launch    - Build and launch Docker + Traefik + PostgreSQL + Metabase stack"
	@echo "  make validate  - Validate UNIX tools, volume mounts, and database connectivity"
	@echo "  make generate  - Generate random raw datasets (CSV, JSON, Apache logs)"
	@echo "  make pipeline  - Run full UNIX ETL + analysis + Iragi audit pipeline"
	@echo "  make audit     - Run Iragi data quality scan, DataContract DLQ, and reconciliation"
	@echo "  make test      - Execute isolated pytest suite and shellcheck"
	@echo "  make backup    - Create SHA-256 verified archive of datasets and PostgreSQL"
	@echo "  make down      - Stop running Docker services"

launch:
	./bin/launch.sh

validate:
	./scripts/etl/validate_env.sh

generate:
	$(PYTHON) -m scripts.etl.generate_data

pipeline:
	./scripts/etl/run_pipeline.sh

audit:
	$(PYTHON) -m scripts.etl.audit_quality

test:
	./bin/test.sh

backup:
	./bin/backup.sh

down:
	docker compose down
