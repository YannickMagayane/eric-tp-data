"""Phase 4 end-to-end integration tests: live Docker stack, PostgreSQL, Metabase, and docs.

Verifies:
1. Non-root execution and UNIX environment validation inside the ``dev`` container.
2. Live PostgreSQL container ingestion via ``load_postgres.sh`` and analytical SQL
   queries across the 9 French cities.
3. Live Metabase health endpoint and Traefik routing readiness.
4. Phase 4 documentation deliverables: installation/usage guide and presentation slides PDF.

Example:
    Run the full end-to-end integration test suite::

        $ ./bin/test.sh
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_dev_container_non_root_and_env_validation() -> None:
    """Verify ``dev`` container runs as UID 1000 non-root and passes ``validate_env.sh``.

    :raises AssertionError: If container runs as root or misses required UNIX/Python tools.

    Example:
        >>> test_dev_container_non_root_and_env_validation()
    """
    uid_res = subprocess.run(
        ["docker", "compose", "run", "--rm", "--no-deps", "-T", "dev", "id", "-u"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert uid_res.stdout.strip() == "1000"

    val_res = subprocess.run(
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "dev",
            "./scripts/etl/validate_env.sh",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert val_res.returncode == 0, f"Container validate_env.sh failed: {val_res.stderr}"


def test_end_to_end_postgres_and_metabase_integration() -> None:
    """Verify end-to-end loading into PostgreSQL and live Metabase health via Traefik.

    :raises AssertionError: If PostgreSQL row counts, French city coverage, or Metabase fail.

    Example:
        >>> test_end_to_end_postgres_and_metabase_integration()
    """
    status_file = PROJECT_ROOT / "data/reports/pipeline_status.json"
    expected_clean = json.loads(status_file.read_text(encoding="utf-8"))["clean_rows"]

    load_res = subprocess.run(
        [str(PROJECT_ROOT / "scripts/etl/load_postgres.sh")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert load_res.returncode == 0, f"load_postgres.sh failed: {load_res.stderr}"

    sql_check = (
        "SELECT "
        "(SELECT COUNT(*) FROM couriers),"
        "(SELECT COUNT(*) FROM deliveries),"
        "(SELECT COUNT(*) FROM web_access_logs),"
        "(SELECT COUNT(DISTINCT ville) FROM deliveries WHERE ville IN ('Paris', 'Lyon', 'Marseille', 'Strasbourg'));"
    )
    psql_res = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "logistics",
            "-d",
            "logistics_db",
            "-t",
            "-A",
            "-F",
            ",",
            "-c",
            sql_check,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    couriers_n, deliveries_n, logs_n, cities_n = [
        int(x) for x in psql_res.stdout.strip().split(",")
    ]
    assert 20 <= couriers_n <= 50
    assert deliveries_n == expected_clean
    assert logs_n >= 500
    assert cities_n == 4

    req = urllib.request.Request(
        "http://127.0.0.1:8080/api/health",
        headers={"Host": "metabase.localhost"},
    )
    deadline = time.time() + 45
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                payload = json.loads(resp.read().decode("utf-8"))
                assert payload.get("status") == "ok"
                last_err = None
                break
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            last_err = exc
            time.sleep(3)
    if last_err is not None:
        raise AssertionError(f"Metabase healthcheck via Traefik failed: {last_err}")


def test_phase4_installation_guide_and_slides_deliverables() -> None:
    """Verify the installation/operations guide and compiled presentation slides exist.

    :raises AssertionError: If the guide or compiled slides PDF is missing or incomplete.

    Example:
        >>> test_phase4_installation_guide_and_slides_deliverables()
    """
    guide_path = PROJECT_ROOT / "docs/GUIDE_INSTALLATION_UTILISATION.md"
    assert guide_path.is_file(), "Missing docs/GUIDE_INSTALLATION_UTILISATION.md"
    guide_text = guide_path.read_text(encoding="utf-8")
    for keyword in ("Traefik", "PostgreSQL", "Metabase", "iragi", "Paris", "MODE=extended"):
        assert keyword in guide_text

    slides_tex = PROJECT_ROOT / "docs/slides.tex"
    slides_pdf = PROJECT_ROOT / "docs/slides.pdf"
    assert slides_tex.is_file(), "Missing docs/slides.tex"
    assert slides_pdf.is_file(), "Missing compiled docs/slides.pdf"
    pdf_bytes = slides_pdf.read_bytes()
    assert len(pdf_bytes) > 15_000
    assert pdf_bytes[:4] == b"%PDF"
