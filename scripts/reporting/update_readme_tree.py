"""Auto-generate and update the ordered repository tree in ``README.md``.

Scans the project directory structure in logical execution order (root config,
``bin/``, ``scripts/``, ``sql/``, ``data/``, ``backups/``, ``docs/``, ``tests/``)
and updates the ``<!-- TREE:START --> ... <!-- TREE:END -->`` block inside
``README.md`` so documentation stays synchronized with actual project files.

Example:
    Run directly from the repository root or via Make::

        $ docker compose exec -T dev python3 -m scripts.reporting.update_readme_tree
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT_ORDER = [
    ("Dockerfile", "Image multi-stage Debian + Python 3.14 non-root (appuser)"),
    ("docker-compose.yml", "Services traefik, db, dev, dashboard + healthchecks"),
    ("Makefile", "Commandes unifiees (generate-data, pipeline, charts, report, test)"),
    ("requirements.txt", "Dependances Python installees dans l'image Docker (iragi, pytest)"),
    ("README.md", "Documentation technique principale"),
    ("EXAMEN system UNIX.pdf", "Cahier des charges officiel de l'examen"),
]

BIN_ORDER = [
    ("launch.sh", "Construction, demarrage Docker et validation runtime"),
    ("test.sh", "Execution isolee pytest + shellcheck"),
    ("backup.sh", "Sauvegarde pg_dump + tar.gz verifiee par SHA-256"),
]

SCRIPTS_ORDER = [
    ("etl/", "common.sh, validate_env.sh, generate_data.py, clean/transform/run/load, audit_quality.py"),
    ("analysis/", "analyze_data.sh (stats, quartiles, Pearson r, .dat)"),
    ("reporting/", "generate_charts.sh, generate_report.sh, render_report.py, setup_metabase.py, update_readme_tree.py"),
]

SQL_ORDER = [
    ("schema.sql", "Schema PostgreSQL (couriers, deliveries, web_access_logs, iragi_audit_metrics)"),
    ("queries.sql", "Requetes SQL analytiques pour Metabase"),
]

DOCS_ORDER = [
    ("GUIDE_INSTALLATION_UTILISATION.md", "Guide detaille d'installation et d'utilisation"),
    ("SCRIPT_VIDEO_DEMO.md", "Trame de presentation pour la video YouTube"),
    ("rapport.tex / rapport.pdf", "Rapport universitaire LaTeX et PDF compile"),
    ("slides.tex / slides.pdf", "Presentation Beamer PDF (10 diapositives)"),
]

TESTS_ORDER = [
    ("test_foundation.py", "Tests infrastructure Docker, Traefik, donnees et iragi"),
    ("test_phase2_pipelines.py", "Tests pipelines UNIX (clean, transform, analyze, run)"),
    ("test_phase3_reporting.py", "Tests gnuplot, rapports MD/HTML, LaTeX et certification iragi"),
    ("test_phase4_e2e.py", "Tests bout-en-bout PostgreSQL, Metabase et livrables"),
]


def _format_entry(prefix: str, name: str, comment: str, width: int = 44) -> str:
    """Format one aligned tree line with an inline description comment.

    :param prefix: Tree indentation and connector characters.
    :type prefix: str
    :param name: File or directory label.
    :type name: str
    :param comment: Short French description aligned on the right.
    :type comment: str
    :param width: Target column width before ``#``.
    :type width: int
    :return: Formatted single tree line.
    :rtype: str

    Example:
        >>> _format_entry("├── ", "Makefile", "Commandes unifiees", width=24)
        '├── Makefile            # Commandes unifiees'
    """
    left = f"{prefix}{name}"
    padding = max(2, width - len(left))
    return f"{left}{' ' * padding}# {comment}"


def build_project_tree(project_root: Path) -> str:
    """Build the ordered Markdown code block describing the repository layout.

    :param project_root: Absolute path to the project root directory.
    :type project_root: Path
    :return: Formatted ``text`` fenced code block.
    :rtype: str

    Example:
        >>> from pathlib import Path
        >>> block = build_project_tree(Path("."))
        >>> block.startswith("```text")
        True
    """
    lines = ["```text", "."]

    for filename, desc in ROOT_ORDER:
        if (project_root / filename).exists():
            lines.append(_format_entry("├── ", filename, desc))

    if (project_root / "bin").is_dir():
        lines.append("├── bin/")
        present_bin = [(f, d) for f, d in BIN_ORDER if (project_root / "bin" / f).exists()]
        for idx, (fname, desc) in enumerate(present_bin):
            conn = "│   └── " if idx == len(present_bin) - 1 else "│   ├── "
            lines.append(_format_entry(conn, fname, desc))

    if (project_root / "scripts").is_dir():
        lines.append("├── scripts/")
        present_scripts = [
            (f, d) for f, d in SCRIPTS_ORDER if (project_root / "scripts" / f.rstrip("/")).is_dir()
        ]
        for idx, (dname, desc) in enumerate(present_scripts):
            conn = "│   └── " if idx == len(present_scripts) - 1 else "│   ├── "
            lines.append(_format_entry(conn, dname, desc))

    if (project_root / "sql").is_dir():
        lines.append("├── sql/")
        present_sql = [(f, d) for f, d in SQL_ORDER if (project_root / "sql" / f).exists()]
        for idx, (fname, desc) in enumerate(present_sql):
            conn = "│   └── " if idx == len(present_sql) - 1 else "│   ├── "
            lines.append(_format_entry(conn, fname, desc))

    data_dir = project_root / "data"
    if data_dir.is_dir():
        lines.append("├── data/")
        viz_count = len(list((data_dir / "visualizations").glob("*.png"))) if (data_dir / "visualizations").is_dir() else 0
        data_items = [
            ("raw/", "Donnees brutes (CSV, JSON, access.log) + generation_manifest.json"),
            ("processed/", "Donnees nettoyees, enrichies, DLQ et fichiers .dat"),
            ("reports/", "Audits JSON, stats, anomalies, lineage_manifest.json, MD/HTML"),
            ("visualizations/", f"{viz_count} graphiques PNG generes par gnuplot (01 a {viz_count:02d})" if viz_count else "Graphiques PNG generes par gnuplot"),
        ]
        for idx, (dname, desc) in enumerate(data_items):
            conn = "│   └── " if idx == len(data_items) - 1 else "│   ├── "
            lines.append(_format_entry(conn, dname, desc))

    if (project_root / "backups").is_dir():
        lines.append(_format_entry("├── ", "backups/", "Dumps SQL PostgreSQL et archives .tar.gz + empreintes .sha256"))

    if (project_root / "docs").is_dir():
        lines.append("├── docs/")
        lines.extend(
            _format_entry("│   └── " if idx == len(DOCS_ORDER) - 1 else "│   ├── ", fname, desc)
            for idx, (fname, desc) in enumerate(DOCS_ORDER)
        )

    if (project_root / "tests").is_dir():
        lines.append("└── tests/")
        present_tests = [(f, d) for f, d in TESTS_ORDER if (project_root / "tests" / f).exists()]
        for idx, (fname, desc) in enumerate(present_tests):
            conn = "    └── " if idx == len(present_tests) - 1 else "    ├── "
            lines.append(_format_entry(conn, fname, desc))

    lines.append("```")
    return "\n".join(lines)


def update_readme_tree(project_root: Path | None = None) -> bool:
    """Update the repository tree block inside ``README.md``.

    :param project_root: Optional root directory; defaults to repository root.
    :type project_root: Path | None
    :return: ``True`` if ``README.md`` was modified, ``False`` if already up to date.
    :rtype: bool
    :raises FileNotFoundError: If ``README.md`` does not exist.

    Example:
        >>> # changed = update_readme_tree()
    """
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    readme_path = root / "README.md"
    if not readme_path.is_file():
        raise FileNotFoundError(f"README.md not found in {root}")

    content = readme_path.read_text(encoding="utf-8")
    tree_block = build_project_tree(root)
    replacement = f"<!-- TREE:START -->\n{tree_block}\n<!-- TREE:END -->"

    pattern = re.compile(r"<!-- TREE:START -->.*?<!-- TREE:END -->", re.DOTALL)
    if pattern.search(content):
        updated = pattern.sub(replacement, content, count=1)
    else:
        section_pattern = re.compile(
            r"(## 10\. Structure des Repertoires\s*\n\s*\n)```text.*?```",
            re.DOTALL,
        )
        if not section_pattern.search(content):
            raise ValueError("Section '## 10. Structure des Repertoires' not found in README.md")
        updated = section_pattern.sub(rf"\1{replacement}", content, count=1)

    if updated == content:
        return False

    readme_path.write_text(updated, encoding="utf-8")
    return True


if __name__ == "__main__":
    changed = update_readme_tree()
    print("README.md tree updated." if changed else "README.md tree already up to date.")
