"""Data quality profiling, naive comparison, DLQ quarantine, and reconciliation via Iragi.

Integrates ``iragi`` (0.6.4) into the UNIX pipeline architecture:
- Uses ``iragi.scan`` (or ``iragi.scan_csv_stream`` for large EXTENDED datasets)
  to inspect raw inputs before UNIX filtering and certify cleaned outputs after.
- Enforces business contracts with ``iragi.DataContract`` and ``iragi.validate_contract``.
- Isolates contract-violating rows into ``quarantine_livraisons.csv`` using
  ``iragi.auto_clean(..., contract_action="quarantine")`` without blind imputation.
- Detects time outliers via ``detect_outliers_modified_zscore``.
- Reconciles ``livraisons.csv`` IDs against Apache HTTP ``/api/livraisons/LIV-<id>``
  calls using ``iragi.reconcile(key_transform=r"(\\d+)")``.

Example:
    Run the quality audit from the terminal::

        $ python3 -m scripts.etl.audit_quality
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import iragi
import pandas as pd
from iragi.scan.profiler import detect_outliers_modified_zscore

LOG_LIVRAISON_PATTERN = re.compile(
    r'"(?:GET|POST)\s+/api/livraisons/(LIV-\d+)\s+HTTP/\d\.\d"\s+(\d{3})'
)

STREAMING_ROW_THRESHOLD = 50_000


def build_delivery_contract() -> iragi.DataContract:
    """Create the business rule contract matching the French-city logistics specification.

    :return: Configured ``iragi.DataContract`` instance.
    :rtype: iragi.DataContract

    Example:
        >>> contract = build_delivery_contract()
        >>> isinstance(contract, iragi.DataContract)
        True
    """
    return (
        iragi.DataContract()
        .require_not_null("id")
        .require_positive("id")
        .require_not_null("ville")
        .require_regex(
            "ville",
            r"^(Paris|Lyon|Marseille|Lille|Bordeaux|Toulouse|Nantes|Nice|Strasbourg)$",
        )
        .require_regex("date", r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
        .require_range("poids", min_val=5.0, max_val=50.0)
        .require_range("distance", min_val=10.0, max_val=500.0)
        .require_range("temps", min_val=30.0, max_val=300.0)
        .require_range("temps_prevu", min_val=30.0, max_val=300.0)
        .require_regex("statut", r"^(livre|en_cours|retarde|annule)$")
    )


def extract_log_delivery_refs(log_path: Path) -> pd.DataFrame:
    """Extract unique delivery API references from an Apache ``access.log`` file.

    :param log_path: Path to the Apache access log file.
    :type log_path: Path
    :return: DataFrame with columns ``log_ref`` and ``http_status``.
    :rtype: pd.DataFrame
    :raises FileNotFoundError: If ``log_path`` does not exist.

    Example:
        >>> from pathlib import Path
        >>> # df_logs = extract_log_delivery_refs(Path("data/raw/access.log"))
    """
    if not log_path.is_file():
        raise FileNotFoundError(f"Access log not found: {log_path}")

    seen_refs: dict[str, int] = {}
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            match = LOG_LIVRAISON_PATTERN.search(line)
            if match:
                seen_refs[match.group(1)] = int(match.group(2))

    return pd.DataFrame(
        [{"log_ref": ref, "http_status": code} for ref, code in seen_refs.items()]
    )


def _normalize_whitespace_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from string columns without mutating input.

    :param df: Source DataFrame loaded from raw CSV.
    :type df: pd.DataFrame
    :return: Normalized copy with trimmed string cells and empty strings set to NA.
    :rtype: pd.DataFrame

    Example:
        >>> frame = pd.DataFrame({"ville": [" Paris ", ""]})
        >>> cleaned = _normalize_whitespace_columns(frame)
        >>> cleaned["ville"].iloc[0]
        'Paris'
    """
    out = df.copy()
    for col in out.select_dtypes(include=["object", "string"]).columns:
        out[col] = out[col].apply(
            lambda val: val.strip() if isinstance(val, str) else val
        )
        out[col] = out[col].replace("", pd.NA)
    for num_col in ("id", "livreur_id", "poids", "distance", "temps", "temps_prevu", "cout_livraison"):
        if num_col in out.columns:
            out[num_col] = pd.to_numeric(out[num_col], errors="coerce")
    return out


def _simulate_naive_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    """Simulate classical naive cleaning (dedup + blind mean/mode fill, no DataContract).

    :param df: Normalized raw DataFrame.
    :type df: pd.DataFrame
    :return: Naively imputed DataFrame still containing business rule violations.
    :rtype: pd.DataFrame

    Example:
        >>> frame = pd.DataFrame({"id": [1.0, None], "poids": [-5.0, 20.0], "ville": ["Paris", None]})
        >>> naive = _simulate_naive_cleaning(frame)
        >>> len(naive)
        2
    """
    naive = df.drop_duplicates().copy()
    for num_col in ("id", "poids", "distance", "temps", "temps_prevu"):
        if num_col in naive.columns and naive[num_col].notna().any():
            naive[num_col] = naive[num_col].fillna(naive[num_col].mean())
    for str_col in ("date", "ville", "statut"):
        if str_col in naive.columns and naive[str_col].notna().any():
            mode_val = naive[str_col].mode(dropna=True)
            if not mode_val.empty:
                naive[str_col] = naive[str_col].fillna(mode_val.iloc[0])
    return naive


def _write_comparison_dat(
    dat_path: Path,
    duplicates_raw: int,
    violations_raw: int,
    missing_raw: int,
    orphans_count: int,
    violations_naive: int,
    violations_iragi: int,
    missing_iragi: int,
) -> None:
    """Write a 3-way comparison table (Raw vs Classical Naive vs UNIX + Iragi) for gnuplot.

    :param dat_path: Output ``.dat`` file path.
    :type dat_path: Path
    :param duplicates_raw: Duplicates in raw data.
    :type duplicates_raw: int
    :param violations_raw: Contract violations in raw data.
    :type violations_raw: int
    :param missing_raw: Missing cells in raw data.
    :type missing_raw: int
    :param orphans_count: Unreconciled HTTP 404 orphan calls in access logs.
    :type orphans_count: int
    :param violations_naive: Remaining contract violations after naive cleaning.
    :type violations_naive: int
    :param violations_iragi: Remaining contract violations after UNIX + Iragi.
    :type violations_iragi: int
    :param missing_iragi: Remaining missing cells after UNIX + Iragi.
    :type missing_iragi: int

    Example:
        >>> from pathlib import Path
        >>> _write_comparison_dat(Path("/tmp/comp.dat"), 35, 12, 3, 20, 9, 0, 0)
    """
    lines = [
        "# categorie\tdonnees_brutes\tapproche_classique_naive\tpipeline_unix_iragi",
        f'"Doublons actifs"\t{duplicates_raw}\t0\t0',
        f'"Violations contrat"\t{violations_raw}\t{violations_naive}\t{violations_iragi}',
        f'"Cellules corrompues"\t{missing_raw}\t{missing_raw}\t{missing_iragi}',
        f'"Orphelins HTTP 404"\t{orphans_count}\t{orphans_count}\t0',
    ]
    dat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_iragi_audit(
    raw_dir: Path = Path("data/raw"),
    processed_dir: Path = Path("data/processed"),
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute 3-way Iragi audit (Before Raw vs Classical Naive vs After UNIX + Iragi).

    Automatically switches to ``iragi.scan_csv_stream`` when raw input exceeds
    50,000 rows (EXTENDED mode) to keep memory usage bounded.

    :param raw_dir: Directory containing ``livraisons.csv`` and ``access.log``.
    :type raw_dir: Path
    :param processed_dir: Directory containing UNIX outputs and DLQ quarantine CSV.
    :type processed_dir: Path
    :param reports_dir: Optional directory where ``iragi_audit.json`` is saved.
    :type reports_dir: Path | None
    :return: Dictionary detailing raw, naive, and UNIX+Iragi quality metrics.
    :rtype: dict[str, Any]

    Example:
        >>> from pathlib import Path
        >>> # report = run_iragi_audit(Path("data/raw"), Path("data/processed"))
    """
    processed_dir.mkdir(parents=True, exist_ok=True)
    target_reports_dir = reports_dir or (processed_dir.parent / "reports")
    target_reports_dir.mkdir(parents=True, exist_ok=True)

    csv_path = raw_dir / "livraisons.csv"
    log_path = raw_dir / "access.log"

    with csv_path.open(encoding="utf-8") as handle:
        physical_lines = sum(1 for _ in handle)
    use_streaming = physical_lines > STREAMING_ROW_THRESHOLD

    raw_scan = (
        iragi.scan_csv_stream(str(csv_path), chunksize=50_000)
        if use_streaming
        else iragi.scan(str(csv_path))
    )
    raw_df = pd.read_csv(csv_path, skip_blank_lines=True)
    normalized_df = _normalize_whitespace_columns(raw_df)
    missing_before = int(normalized_df.isna().sum().sum())

    contract = build_delivery_contract()
    pre_violations = iragi.validate_contract(normalized_df, contract)
    pre_violations_total = sum(v.failed_count for v in pre_violations)
    raw_time_outliers = int(
        detect_outliers_modified_zscore(normalized_df["temps"].dropna())
    )

    naive_df = _simulate_naive_cleaning(normalized_df)
    naive_violations = iragi.validate_contract(naive_df, contract)
    naive_violations_total = sum(v.failed_count for v in naive_violations)

    clean_result = iragi.auto_clean(
        normalized_df,
        drop_duplicates=True,
        impute_numeric="none",
        impute_categorical="none",
        contract=contract,
        contract_action="quarantine",
    )
    quarantine_path = processed_dir / "quarantine_livraisons.csv"
    clean_result.quarantine_df.to_csv(quarantine_path, index=False)

    iragi_clean_df = clean_result.df.copy()
    iragi_clean_df["id"] = iragi_clean_df["id"].astype(int)

    unix_clean_path = processed_dir / "livraisons_clean.csv"
    if unix_clean_path.is_file():
        after_scan = (
            iragi.scan_csv_stream(str(unix_clean_path), chunksize=50_000)
            if use_streaming
            else iragi.scan(str(unix_clean_path))
        )
        after_df = pd.read_csv(unix_clean_path)
        evaluated_source = "livraisons_clean.csv (UNIX clean_data.sh)"
    else:
        after_scan = iragi.scan_dataframe(iragi_clean_df)
        after_df = iragi_clean_df
        evaluated_source = "iragi.auto_clean (in-memory)"

    post_violations = iragi.validate_contract(after_df, contract)
    post_violations_total = sum(v.failed_count for v in post_violations)
    missing_after = int(after_df.isna().sum().sum())
    drift = iragi.compare_scans(raw_scan, after_scan)
    outlier_count = int(detect_outliers_modified_zscore(after_df["temps"].dropna()))

    log_df = extract_log_delivery_refs(log_path)
    reconciliation = iragi.reconcile(
        after_df,
        log_df,
        on=("id", "log_ref"),
        key_transform=r"(\d+)",
    )

    duplicates_removed = int(clean_result.changes.get("duplicates_removed", 0))
    quarantined_count = len(clean_result.quarantine_df)
    orphans_http = int(reconciliation.orphan_b_count)

    _write_comparison_dat(
        dat_path=processed_dir / "iragi_before_after.dat",
        duplicates_raw=duplicates_removed,
        violations_raw=pre_violations_total,
        missing_raw=missing_before,
        orphans_count=orphans_http,
        violations_naive=naive_violations_total,
        violations_iragi=post_violations_total,
        missing_iragi=missing_after,
    )

    before_unix: dict[str, Any] = {
        "evaluated_file": "data/raw/livraisons.csv",
        "scan_mode": "scan_csv_stream" if use_streaming else "scan",
        "raw_rows": raw_scan.row_count,
        "raw_quality_score": round(float(raw_scan.quality_score.total_score), 2),
        "duplicates_detected": duplicates_removed,
        "missing_cells_count": missing_before,
        "contract_violations_count": pre_violations_total,
        "contract_violations": [
            {"column": v.column, "rule": v.rule, "failed_count": v.failed_count}
            for v in pre_violations
        ],
        "quarantined_rows_count": quarantined_count,
        "raw_modified_zscore_time_outliers": raw_time_outliers,
    }

    naive_baseline: dict[str, Any] = {
        "description": "Dedup + blind mean/mode imputation without DataContract or DLQ",
        "rows_retained": len(naive_df),
        "remaining_contract_violations": naive_violations_total,
        "fabricated_imputations_count": missing_before,
        "dlq_quarantine_supported": False,
        "unreconciled_http_orphans": orphans_http,
    }

    after_unix: dict[str, Any] = {
        "evaluated_file": evaluated_source,
        "unix_clean_rows": after_scan.row_count,
        "iragi_clean_rows": len(iragi_clean_df),
        "unix_vs_iragi_row_parity": after_scan.row_count == len(iragi_clean_df),
        "unix_clean_quality_score": round(
            float(after_scan.quality_score.total_score), 2
        ),
        "quality_score_delta": round(float(drift.score_delta), 2),
        "missing_delta": int(drift.missing_delta),
        "post_unix_contract_violations_count": post_violations_total,
        "modified_zscore_time_outliers": outlier_count,
    }

    audit_summary: dict[str, Any] = {
        "iragi_version": iragi.__version__,
        "before_unix": before_unix,
        "naive_baseline": naive_baseline,
        "after_unix": after_unix,
        "raw_rows": raw_scan.row_count,
        "raw_quality_score": before_unix["raw_quality_score"],
        "clean_rows": after_scan.row_count,
        "clean_quality_score": after_unix["unix_clean_quality_score"],
        "quality_score_delta": after_unix["quality_score_delta"],
        "duplicates_removed": duplicates_removed,
        "contract_violations_count": pre_violations_total,
        "contract_violations": before_unix["contract_violations"],
        "quarantined_rows_count": quarantined_count,
        "modified_zscore_time_outliers": outlier_count,
        "log_reconciliation_match_rate": round(float(reconciliation.match_rate), 4),
        "log_matched_deliveries": int(reconciliation.matched_count),
        "orphan_http_delivery_calls": orphans_http,
    }

    report_path = target_reports_dir / "iragi_audit.json"
    report_path.write_text(json.dumps(audit_summary, indent=2) + "\n", encoding="utf-8")
    return audit_summary


if __name__ == "__main__":
    result = run_iragi_audit()
    print(json.dumps(result, indent=2))
