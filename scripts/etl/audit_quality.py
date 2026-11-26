"""Data quality profiling, contract quarantine, and reconciliation via Iragi.

Demonstrates how ``iragi`` intervenes both BEFORE and AFTER the UNIX ETL pipeline:
1. BEFORE UNIX cleaning (``data/raw/livraisons.csv``): profiles raw anomalies,
   evaluates ``iragi.DataContract``, and isolates corrupt rows into a Dead-Letter
   Queue (``quarantine_livraisons.csv``) via ``iragi.auto_clean``.
2. AFTER UNIX cleaning (``data/processed/livraisons_clean.csv``): re-scans and
   re-validates the output of ``clean_data.sh``, computing ``iragi.compare_scans``
   drift deltas and verifying exact row parity between UNIX filters and ``iragi``.
3. Cross-source reconciliation (``iragi.reconcile``) between deliveries and
   Apache HTTP access logs.

Example:
    Run the before/after quality audit from the terminal::

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
    r'"(?:GET|POST|PUT|DELETE)\s+/api/livraisons/(LIV-\d+)\s+HTTP/\d\.\d"\s+(\d{3})'
)


def build_delivery_contract() -> iragi.DataContract:
    """Create the business rule contract matching the project dataset specification.

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
        .require_regex("date", r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
        .require_range("poids", min_val=5.0, max_val=50.0)
        .require_range("distance", min_val=10.0, max_val=500.0)
        .require_range("temps", min_val=30.0, max_val=300.0)
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
    for line in log_path.read_text(encoding="utf-8").splitlines():
        match = LOG_LIVRAISON_PATTERN.search(line)
        if match:
            ref_code, status_str = match.group(1), match.group(2)
            seen_refs[ref_code] = int(status_str)

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
    for num_col in ("id", "poids", "distance", "temps"):
        if num_col in out.columns:
            out[num_col] = pd.to_numeric(out[num_col], errors="coerce")
    return out


def _write_before_after_dat(
    dat_path: Path,
    duplicates_before: int,
    violations_before: int,
    missing_before: int,
    quarantine_before: int,
    violations_after: int,
    missing_after: int,
) -> None:
    """Write a gnuplot-compatible data table comparing pre- and post-UNIX anomalies.

    :param dat_path: Output ``.dat`` file path.
    :type dat_path: Path
    :param duplicates_before: Exact duplicate rows detected in raw input.
    :type duplicates_before: int
    :param violations_before: DataContract rule failures detected in raw input.
    :type violations_before: int
    :param missing_before: Missing cell count in raw input.
    :type missing_before: int
    :param quarantine_before: Rows isolated into DLQ quarantine.
    :type quarantine_before: int
    :param violations_after: Remaining contract violations after UNIX cleaning.
    :type violations_after: int
    :param missing_after: Remaining missing cells after UNIX cleaning.
    :type missing_after: int

    Example:
        >>> from pathlib import Path
        >>> _write_before_after_dat(Path("/tmp/iragi_ba.dat"), 20, 9, 3, 8, 0, 0)
    """
    lines = [
        '# indicator\tavant_nettoyage\tapres_nettoyage',
        f'"Doublons"\t{duplicates_before}\t0',
        f'"Violations Contrat"\t{violations_before}\t{violations_after}',
        f'"Quarantaine DLQ"\t{quarantine_before}\t0',
        f'"Cellules Vides"\t{missing_before}\t{missing_after}',
    ]
    dat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_iragi_audit(
    raw_dir: Path = Path("data/raw"),
    processed_dir: Path = Path("data/processed"),
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute Before-and-After Iragi profiling, DLQ quarantine, and log reconciliation.

    :param raw_dir: Directory containing ``livraisons.csv`` and ``access.log``.
    :type raw_dir: Path
    :param processed_dir: Directory containing UNIX outputs and DLQ quarantine CSV.
    :type processed_dir: Path
    :param reports_dir: Optional directory where ``iragi_audit.json`` is saved.
    :type reports_dir: Path | None
    :return: Dictionary of pre-UNIX and post-UNIX scores, parity, DLQ, and match rates.
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

    # 1. BEFORE: Inspect raw dataset prior to UNIX pipeline
    raw_scan = iragi.scan(str(csv_path))
    raw_df = pd.read_csv(csv_path, skip_blank_lines=True)
    normalized_df = _normalize_whitespace_columns(raw_df)
    missing_before = int(normalized_df.isna().sum().sum())

    # Export raw numeric distance/temps pairs (including outliers) for visual comparison
    raw_numeric_pairs = normalized_df[["distance", "temps"]].dropna()
    raw_scatter_lines = ["# distance\ttemps"] + [
        f"{int(row.distance)}\t{int(row.temps)}"
        for row in raw_numeric_pairs.itertuples(index=False)
    ]
    (processed_dir / "raw_distance_vs_temps.dat").write_text(
        "\n".join(raw_scatter_lines) + "\n", encoding="utf-8"
    )

    contract = build_delivery_contract()
    pre_violations = iragi.validate_contract(normalized_df, contract)
    pre_violations_total = sum(v.failed_count for v in pre_violations)

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

    # 2. AFTER: Certify actual UNIX clean_data.sh output if present, else Iragi clean df
    unix_clean_path = processed_dir / "livraisons_clean.csv"
    if unix_clean_path.is_file():
        after_scan = iragi.scan(str(unix_clean_path))
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

    # 3. Cross-source reconciliation between clean deliveries and Apache HTTP logs
    log_df = extract_log_delivery_refs(log_path)
    reconciliation = iragi.reconcile(
        after_df,
        log_df,
        on=("id", "log_ref"),
        key_transform=r"(\d+)",
    )

    duplicates_removed = int(clean_result.changes.get("duplicates_removed", 0))
    quarantined_count = len(clean_result.quarantine_df)

    _write_before_after_dat(
        dat_path=processed_dir / "iragi_before_after.dat",
        duplicates_before=duplicates_removed,
        violations_before=pre_violations_total,
        missing_before=missing_before,
        quarantine_before=quarantined_count,
        violations_after=post_violations_total,
        missing_after=missing_after,
    )

    before_unix: dict[str, Any] = {
        "evaluated_file": "data/raw/livraisons.csv",
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
        "orphan_http_delivery_calls": int(reconciliation.orphan_b_count),
    }

    report_path = target_reports_dir / "iragi_audit.json"
    report_path.write_text(json.dumps(audit_summary, indent=2) + "\n", encoding="utf-8")
    return audit_summary


if __name__ == "__main__":
    result = run_iragi_audit()
    print(json.dumps(result, indent=2))
