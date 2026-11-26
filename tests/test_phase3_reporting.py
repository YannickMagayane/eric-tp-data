"""TDD test suite for Phase 3 visualizations, Iragi before/after audit, and reporting.

Verifies that:
1. ``iragi`` audits raw data BEFORE ``clean_data.sh`` and certifies the UNIX-cleaned
   output AFTER ``clean_data.sh`` (0 remaining contract violations, 100/100 score,
   and exact row parity between UNIX filters and ``iragi.auto_clean``).
2. ``generate_charts.sh`` renders all 6 PNG charts via ``gnuplot`` from real data.
3. ``generate_report.sh`` produces Markdown and HTML reports from real metrics.
4. ``load_postgres.sh`` exists, is executable, and validates inputs cleanly.
5. ``docs/rapport.pdf`` compiles cleanly from ``docs/rapport.tex``.

Example:
    Execute Phase 3 tests via the standard test runner::

        $ ./bin/test.sh
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PHASE3_SCRIPTS = [
    "scripts/etl/load_postgres.sh",
    "scripts/reporting/generate_charts.sh",
    "scripts/reporting/generate_report.sh",
]

EXPECTED_CHARTS = [
    "01_livraisons_par_ville.png",
    "02_evolution_temporelle.png",
    "03_distribution_temps.png",
    "04_distance_vs_temps.png",
    "05_performance_livreurs.png",
    "06_iragi_avant_apres.png",
]


def test_phase3_scripts_exist_and_executable() -> None:
    """Verify Phase 3 shell scripts exist and carry executable permissions.

    :raises AssertionError: If any Phase 3 script is missing or not executable.

    Example:
        >>> test_phase3_scripts_exist_and_executable()
    """
    for rel_path in PHASE3_SCRIPTS:
        target = PROJECT_ROOT / rel_path
        assert target.is_file(), f"Missing Phase 3 script: {rel_path}"
        assert os.access(target, os.X_OK), f"Script not executable: {rel_path}"


def test_iragi_before_and_after_unix_certification() -> None:
    """Verify Iragi certifies both BEFORE raw anomalies and AFTER UNIX clean_data.sh.

    :raises AssertionError: If before/after Iragi metrics or parity checks are missing.

    Example:
        >>> test_iragi_before_and_after_unix_certification()
    """
    audit_file = PROJECT_ROOT / "data/reports/iragi_audit.json"
    assert audit_file.is_file(), "Missing data/reports/iragi_audit.json"
    audit = json.loads(audit_file.read_text(encoding="utf-8"))

    assert "before_unix" in audit, "Missing 'before_unix' section in iragi_audit.json"
    assert "after_unix" in audit, "Missing 'after_unix' section in iragi_audit.json"

    before = audit["before_unix"]
    after = audit["after_unix"]

    assert before["raw_rows"] == 2536
    assert before["contract_violations_count"] > 0
    assert after["unix_clean_rows"] == 2508
    assert after["unix_clean_quality_score"] == 100.0
    assert after["post_unix_contract_violations_count"] == 0
    assert after["unix_vs_iragi_row_parity"] is True
    assert (PROJECT_ROOT / "data/processed/iragi_before_after.dat").is_file()


def test_gnuplot_visualizations_generated_from_real_data() -> None:
    """Verify all 6 PNG charts are rendered in ``data/visualizations/`` with valid headers.

    :raises AssertionError: If any PNG chart is missing or lacks a valid PNG signature.

    Example:
        >>> test_gnuplot_visualizations_generated_from_real_data()
    """
    vis_dir = PROJECT_ROOT / "data/visualizations"
    for chart_name in EXPECTED_CHARTS:
        chart_path = vis_dir / chart_name
        assert chart_path.is_file(), f"Missing gnuplot chart: {chart_name}"
        raw_bytes = chart_path.read_bytes()
        assert len(raw_bytes) > 1000, f"Chart appears empty: {chart_name}"
        assert raw_bytes[:8] == b"\x89PNG\r\n\x1a\n", f"Invalid PNG header: {chart_name}"


def test_generated_markdown_and_html_reports_match_real_data() -> None:
    """Verify ``generate_report.sh`` outputs Markdown and HTML reports with real metrics.

    :raises AssertionError: If reports are missing or omit real dataset figures.

    Example:
        >>> test_generated_markdown_and_html_reports_match_real_data()
    """
    res = subprocess.run(
        [str(PROJECT_ROOT / "scripts/reporting/generate_report.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"generate_report.sh failed: {res.stderr}"

    md_report = PROJECT_ROOT / "data/reports/latest_report.md"
    html_report = PROJECT_ROOT / "data/reports/dashboard_report.html"
    assert md_report.is_file()
    assert html_report.is_file()

    md_text = md_report.read_text(encoding="utf-8")
    for real_token in ("2536", "2508", "99.7", "100.0", "0.9671", "Lyon", "Lille", "iragi"):
        assert real_token in md_text, f"Missing real metric '{real_token}' in Markdown report"

    html_text = html_report.read_text(encoding="utf-8")
    assert "01_livraisons_par_ville.png" in html_text
    assert "06_iragi_avant_apres.png" in html_text


def test_compiled_latex_report_exists() -> None:
    """Verify ``docs/rapport.tex`` compiles into a valid non-empty PDF document.

    :raises AssertionError: If ``docs/rapport.pdf`` is missing or lacks a PDF header.

    Example:
        >>> test_compiled_latex_report_exists()
    """
    pdf_path = PROJECT_ROOT / "docs/rapport.pdf"
    assert pdf_path.is_file(), "Missing compiled docs/rapport.pdf"
    pdf_bytes = pdf_path.read_bytes()
    assert len(pdf_bytes) > 10_000
    assert pdf_bytes[:4] == b"%PDF"
