"""TDD test suite for Phase 3 visualizations, Iragi before/after audit, and reporting.

Verifies:
1. ``iragi`` certifies both raw anomalies (BEFORE) and UNIX-cleaned output (AFTER).
2. All 8 professional PNG charts are rendered via ``gnuplot`` from real processed data.
3. ``generate_report.sh`` produces Markdown and HTML reports matching real French-city data.
4. ``docs/rapport.pdf`` compiles cleanly without BMAD references.

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
    "02_evolution_mensuelle.png",
    "03_taux_retard_par_ville.png",
    "04_distribution_temps.png",
    "05_distance_vs_temps.png",
    "06_repartition_statuts.png",
    "07_performance_livreurs.png",
    "08_anomalies_avant_apres.png",
    "09_impact_donnees_avant_apres_iragi.png",
    "10_reconciliation_http_iragi.png",
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

    assert "before_unix" in audit
    assert "naive_baseline" in audit
    assert "after_unix" in audit

    before = audit["before_unix"]
    naive = audit["naive_baseline"]
    after = audit["after_unix"]

    assert before["raw_rows"] > after["unix_clean_rows"]
    assert before["contract_violations_count"] > 0
    assert naive["remaining_contract_violations"] > 0
    assert after["unix_clean_quality_score"] > before["raw_quality_score"]
    assert after["unix_clean_quality_score"] >= 99.0
    assert after["post_unix_contract_violations_count"] == 0
    assert after["unix_vs_iragi_row_parity"] is True
    assert (PROJECT_ROOT / "data/processed/iragi_before_after.dat").is_file()


def test_gnuplot_visualizations_generated_from_real_data() -> None:
    """Verify all 8 PNG charts are rendered in ``data/visualizations/`` with valid headers.

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

    :raises AssertionError: If reports are missing or omit real French-city dataset figures.

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
    for real_token in ("Paris", "Lyon", "Marseille", "99.75", "iragi"):
        assert real_token in md_text, f"Missing real token '{real_token}' in Markdown report"

    html_text = html_report.read_text(encoding="utf-8")
    assert "01_livraisons_par_ville.png" in html_text
    assert "08_anomalies_avant_apres.png" in html_text


def test_compiled_latex_report_exists() -> None:
    """Verify ``docs/rapport.tex`` complies with title rules and compiles to PDF.

    :raises AssertionError: If title rules or compiled PDF validation fail.

    Example:
        >>> test_compiled_latex_report_exists()
    """
    tex_text = (PROJECT_ROOT / "docs/rapport.tex").read_text(encoding="utf-8")
    assert "Lutumba Miteo Eric" in tex_text
    assert "08_anomalies_avant_apres.png" in tex_text
    assert "09_impact_donnees_avant_apres_iragi.png" in tex_text
    assert "youtu.be" in tex_text
    assert "Paris" in tex_text and "Strasbourg" in tex_text
    assert "bmad" not in tex_text.lower()
    for line in tex_text.splitlines():
        if "PROJET FINAL" in line or "Analyse de Donn" in line:
            assert "iragi" not in line.lower(), "Report title must not contain 'iragi'"

    pdf_path = PROJECT_ROOT / "docs/rapport.pdf"
    assert pdf_path.is_file(), "Missing compiled docs/rapport.pdf"
    pdf_bytes = pdf_path.read_bytes()
    assert len(pdf_bytes) > 20_000
    assert pdf_bytes[:4] == b"%PDF"
