"""Isolated TDD test suite for Phase 2 UNIX ETL, analysis, and orchestration pipelines.

Verifies ``clean_data.sh``, ``transform_data.sh``, ``analyze_data.sh``, and
``run_pipeline.sh`` in isolated temporary directories, cross-checking UNIX
filter outputs against ``iragi`` quality scans and mathematical invariants.

Example:
    Run the Phase 2 pipeline tests via pytest::

        $ ./bin/test.sh
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
from pathlib import Path

import iragi

from scripts.etl.generate_data import DatasetConfig, generate_all_datasets

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PHASE2_SCRIPTS = [
    "scripts/etl/common.sh",
    "scripts/etl/clean_data.sh",
    "scripts/etl/transform_data.sh",
    "scripts/analysis/analyze_data.sh",
    "scripts/etl/run_pipeline.sh",
]


def _prepare_isolated_data_dir(base_dir: Path) -> Path:
    """Populate an isolated ``data/`` directory with seeded synthetic raw files.

    :param base_dir: Temporary directory provided by pytest.
    :type base_dir: Path
    :return: Isolated data root containing ``raw/``, ``processed/``, and ``reports/``.
    :rtype: Path

    Example:
        >>> from pathlib import Path
        >>> # data_root = _prepare_isolated_data_dir(Path("/tmp/demo_phase2"))
    """
    data_dir = base_dir / "data"
    generate_all_datasets(
        DatasetConfig(
            output_dir=data_dir / "raw",
            deliveries_count=1000,
            couriers_count=25,
            access_logs_count=500,
            seed=99,
        )
    )
    return data_dir


def test_phase2_scripts_exist_and_executable() -> None:
    """Verify all Phase 2 shell scripts exist and carry executable permissions.

    :raises AssertionError: If any Phase 2 script is missing or non-executable.

    Example:
        >>> test_phase2_scripts_exist_and_executable()
    """
    for rel_path in PHASE2_SCRIPTS:
        script = PROJECT_ROOT / rel_path
        assert script.is_file(), f"Missing Phase 2 script: {rel_path}"
        if rel_path != "scripts/etl/common.sh":
            assert os.access(script, os.X_OK), f"Script not executable: {rel_path}"


def test_clean_data_pipeline(tmp_path: Path) -> None:
    """Verify ``clean_data.sh`` deduplicates, trims, validates, and reaches 100/100 in Iragi.

    :param tmp_path: Temporary pytest directory for isolated execution.
    :type tmp_path: Path
    :raises AssertionError: If cleaned CSV retains invalid rows, duplicates, or whitespace.

    Example:
        >>> from pathlib import Path
        >>> # test_clean_data_pipeline(Path("/tmp/test_clean"))
    """
    data_dir = _prepare_isolated_data_dir(tmp_path)
    env = {**os.environ, "DATA_DIR": str(data_dir)}

    res = subprocess.run(
        [str(PROJECT_ROOT / "scripts/etl/clean_data.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"clean_data.sh failed: {res.stderr}"

    clean_csv = data_dir / "processed/livraisons_clean.csv"
    couriers_csv = data_dir / "processed/livreurs_clean.csv"
    assert clean_csv.is_file()
    assert couriers_csv.is_file()

    with clean_csv.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    # 1000 base valid rows + 8 trimmed whitespace-padded valid rows = 1008 clean rows
    assert len(rows) == 1008
    ids = [int(r["id"]) for r in rows]
    assert len(ids) == len(set(ids)), "Duplicate IDs remained after clean_data.sh"

    scan_res = iragi.scan(str(clean_csv))
    assert scan_res.quality_score.total_score == 100.0


def test_transform_data_pipeline(tmp_path: Path) -> None:
    """Verify ``transform_data.sh`` computes derived metrics, joins couriers, and exports JSON.

    :param tmp_path: Temporary pytest directory for isolated execution.
    :type tmp_path: Path
    :raises AssertionError: If derived columns, aggregations, or JSON conversions are invalid.

    Example:
        >>> from pathlib import Path
        >>> # test_transform_data_pipeline(Path("/tmp/test_transform"))
    """
    data_dir = _prepare_isolated_data_dir(tmp_path)
    env = {**os.environ, "DATA_DIR": str(data_dir)}

    subprocess.run(
        [str(PROJECT_ROOT / "scripts/etl/clean_data.sh")],
        env=env,
        check=True,
    )
    res = subprocess.run(
        [str(PROJECT_ROOT / "scripts/etl/transform_data.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"transform_data.sh failed: {res.stderr}"

    enriched_csv = data_dir / "processed/livraisons_enriched.csv"
    agg_city_csv = data_dir / "processed/agg_par_ville.csv"
    agg_city_json = data_dir / "processed/agg_par_ville.json"
    agg_month_csv = data_dir / "processed/agg_par_mois.csv"
    agg_status_csv = data_dir / "processed/agg_par_statut.csv"

    for path in (
        enriched_csv,
        agg_city_csv,
        agg_city_json,
        agg_month_csv,
        agg_status_csv,
    ):
        assert path.is_file(), f"Missing transformed file: {path.name}"

    with enriched_csv.open(encoding="utf-8") as handle:
        enriched_rows = list(csv.DictReader(handle))
    assert len(enriched_rows) == 1008
    sample = enriched_rows[0]
    for col in ("speed_kmh", "year_month", "city_couriers_count", "city_avg_rating"):
        assert col in sample and sample[col] != ""

    city_json_data = json.loads(agg_city_json.read_text(encoding="utf-8"))
    assert len(city_json_data) == 9
    assert sum(item["total_deliveries"] for item in city_json_data) == 1008


def test_analyze_and_orchestrator_pipeline(tmp_path: Path) -> None:
    """Verify ``run_pipeline.sh`` orchestrates ETL + analysis, logs steps, and handles errors.

    :param tmp_path: Temporary pytest directory for isolated execution.
    :type tmp_path: Path
    :raises AssertionError: If statistical reports, gnuplot data, or error codes fail.

    Example:
        >>> from pathlib import Path
        >>> # test_analyze_and_orchestrator_pipeline(Path("/tmp/test_orchestrator"))
    """
    data_dir = _prepare_isolated_data_dir(tmp_path)
    env = {**os.environ, "DATA_DIR": str(data_dir)}

    res = subprocess.run(
        [str(PROJECT_ROOT / "scripts/etl/run_pipeline.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"run_pipeline.sh failed: {res.stderr}"

    expected_outputs = [
        data_dir / "reports/stats_descriptives.csv",
        data_dir / "reports/hist_temps.dat",
        data_dir / "reports/correlations.csv",
        data_dir / "reports/anomalies.csv",
        data_dir / "reports/pipeline.log",
        data_dir / "reports/pipeline_status.json",
        data_dir / "processed/par_ville.dat",
        data_dir / "processed/par_date.dat",
        data_dir / "processed/dist_temps.dat",
        data_dir / "processed/distance_vs_temps.dat",
        data_dir / "processed/perf_livreurs.dat",
    ]
    for out_file in expected_outputs:
        assert out_file.is_file(), f"Missing output: {out_file}"

    with (data_dir / "reports/correlations.csv").open(encoding="utf-8") as handle:
        corr_rows = {
            r["pair"]: float(r["pearson_r"]) for r in csv.DictReader(handle)
        }
    assert 0.5 < corr_rows["distance_vs_temps"] <= 1.0

    status_payload = json.loads(
        (data_dir / "reports/pipeline_status.json").read_text(encoding="utf-8")
    )
    assert status_payload["status"] == "SUCCESS"
    assert status_payload["clean_rows"] == 1008

    # Verify explicit error handling on missing raw input directory
    broken_env = {**os.environ, "DATA_DIR": str(tmp_path / "nonexistent_data")}
    fail_res = subprocess.run(
        [str(PROJECT_ROOT / "scripts/etl/run_pipeline.sh")],
        env=broken_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert fail_res.returncode != 0
