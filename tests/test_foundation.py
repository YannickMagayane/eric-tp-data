"""Tests for Phase 1 foundation, random dataset generation, and Iragi audit.

This module verifies directory layout, Docker and Traefik configuration,
operational scripts in ``bin/``, random dataset generation rules, and
quality inspection / reconciliation powered by ``iragi``.

Example:
    Execute the foundation test suite directly with pytest::

        $ .venv/bin/pytest tests/test_foundation.py -v
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = [
    "bin",
    "data/raw",
    "data/processed",
    "data/reports",
    "data/visualizations",
    "scripts/etl",
    "scripts/analysis",
    "scripts/reporting",
    "sql",
    "docs",
    "tests",
]

REQUIRED_FILES = [
    "Dockerfile",
    "docker-compose.yml",
    "Makefile",
    "README.md",
    "bin/launch.sh",
    "bin/test.sh",
    "bin/backup.sh",
    "scripts/etl/validate_env.sh",
    "scripts/etl/generate_data.py",
    "scripts/etl/audit_quality.py",
    "sql/schema.sql",
    "sql/queries.sql",
    "docs/rapport.tex",
]

VALID_CITIES = {
    "Paris",
    "Lyon",
    "Marseille",
    "Lille",
    "Bordeaux",
    "Toulouse",
    "Nantes",
    "Nice",
    "Strasbourg",
}

VALID_STATUSES = {"livre", "en_cours", "retarde", "annule"}
VALID_VEHICLES = {"Velo", "Moto", "Camionnette", "Fourgon"}


def test_project_structure_and_permissions() -> None:
    """Verify required directories, files, and executable script permissions.

    :raises AssertionError: If any required directory, file, or executable bit is missing.

    Example:
        >>> test_project_structure_and_permissions()
    """
    for rel_dir in REQUIRED_DIRS:
        target = PROJECT_ROOT / rel_dir
        assert target.is_dir(), f"Missing directory: {rel_dir}"

    for rel_file in REQUIRED_FILES:
        target = PROJECT_ROOT / rel_file
        assert target.is_file(), f"Missing file: {rel_file}"
        if target.suffix == ".sh":
            assert os.access(target, os.X_OK), f"Script not executable: {rel_file}"


def test_docker_and_traefik_configuration() -> None:
    """Verify multi-stage non-root Dockerfile and Traefik-backed docker-compose.

    :raises AssertionError: If Dockerfile or docker-compose violates architecture rules.

    Example:
        >>> test_docker_and_traefik_configuration()
    """
    dockerfile_text = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.14" in dockerfile_text
    assert " AS " in dockerfile_text
    assert "gnuplot" in dockerfile_text
    assert "jq" in dockerfile_text
    assert "iragi" in dockerfile_text
    assert "USER " in dockerfile_text

    compose_text = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for required_service in ("traefik:", "dev:", "db:", "dashboard:"):
        assert required_service in compose_text
    assert "nginx" not in compose_text.lower()
    assert "caddy" not in compose_text.lower()
    assert "healthcheck:" in compose_text


def test_generate_random_datasets(tmp_path: Path) -> None:
    """Verify random dataset generation meets exam specifications and injects anomalies.

    :param tmp_path: Temporary pytest directory for isolated output verification.
    :type tmp_path: Path
    :raises AssertionError: If generated CSV, JSON, or Apache log files violate constraints.

    Example:
        >>> from pathlib import Path
        >>> test_generate_random_datasets(Path("/tmp/demo_raw"))
    """
    from scripts.etl.generate_data import DatasetConfig, generate_all_datasets

    config = DatasetConfig(
        output_dir=tmp_path,
        deliveries_count=1200,
        couriers_count=30,
        access_logs_count=600,
        seed=42,
    )
    manifest = generate_all_datasets(config)

    csv_path = tmp_path / "livraisons.csv"
    json_path = tmp_path / "livreurs.json"
    log_path = tmp_path / "access.log"

    assert csv_path.is_file()
    assert json_path.is_file()
    assert log_path.is_file()
    assert manifest["deliveries_base_rows"] == 1200
    assert manifest["injected_duplicates"] > 0
    assert manifest["injected_invalid_rows"] > 0

    with csv_path.open(encoding="utf-8") as handle:
        non_empty_lines = [line for line in handle if line.strip()]
    reader = csv.DictReader(non_empty_lines)
    assert reader.fieldnames == [
        "id",
        "date",
        "ville",
        "poids",
        "distance",
        "temps",
        "statut",
    ]
    rows = list(reader)
    assert len(rows) >= 1200

    couriers = json.loads(json_path.read_text(encoding="utf-8"))
    assert 20 <= len(couriers) <= 50
    for courier in couriers:
        assert set(courier.keys()) == {
            "id",
            "nom",
            "ville",
            "experience",
            "note",
            "vehicule",
        }
        assert courier["ville"] in VALID_CITIES
        assert courier["vehicule"] in VALID_VEHICLES
        assert 0 <= courier["experience"] <= 30
        assert 0.0 <= courier["note"] <= 5.0

    log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert 500 <= len(log_lines) <= 2000
    assert "/api/livraisons/LIV-" in log_lines[0]


def test_iragi_quality_audit_and_reconciliation(tmp_path: Path) -> None:
    """Verify Iragi quality scan, DataContract DLQ quarantine, and log reconciliation.

    :param tmp_path: Temporary pytest directory holding generated datasets.
    :type tmp_path: Path
    :raises AssertionError: If Iragi fails to detect seeded violations or reconcile records.

    Example:
        >>> from pathlib import Path
        >>> test_iragi_quality_audit_and_reconciliation(Path("/tmp/demo_audit"))
    """
    from scripts.etl.audit_quality import run_iragi_audit
    from scripts.etl.generate_data import DatasetConfig, generate_all_datasets

    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    generate_all_datasets(
        DatasetConfig(
            output_dir=raw_dir,
            deliveries_count=1000,
            couriers_count=25,
            access_logs_count=500,
            seed=7,
        )
    )

    report = run_iragi_audit(raw_dir=raw_dir, processed_dir=processed_dir)
    assert 0.0 <= report["raw_quality_score"] < 100.0
    assert report["clean_quality_score"] > report["raw_quality_score"]
    assert report["contract_violations_count"] > 0
    assert report["quarantined_rows_count"] > 0
    assert (processed_dir / "quarantine_livraisons.csv").is_file()
    assert 0.0 < report["log_reconciliation_match_rate"] <= 1.0
