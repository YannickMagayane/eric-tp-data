"""Data quality profiling, contract quarantine, and reconciliation via Iragi.

Complements the native UNIX filter pipelines (``sed``, ``awk``, ``sort``,
``uniq``, ``jq``) by providing:
1. Explainable 0-100 quality scores before and after remediation (``iragi.scan``
   and ``iragi.compare_scans``).
2. Business rule validation and Dead-Letter Queue (DLQ) quarantine
   (``iragi.DataContract`` + ``iragi.auto_clean``).
3. Median-based outlier detection (``detect_outliers_modified_zscore``).
4. Cross-source regex reconciliation between ``livraisons.csv`` and ``access.log``
   (``iragi.reconcile``).

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
    r'"(?:GET|POST|PUT|DELETE)\s+/api/livraisons/(LIV-\d+)\s+HTTP/\d\.\d"\s+(\d{3})'
)


def build_delivery_contract() -> iragi.DataContract:
    """Create the business rule contract matching the project dataset specification.

    Enforces non-null identifiers and cities, ISO-8601 dates, valid calendar
    months/days, weight in [5, 50] kg, distance in [10, 500] km, delivery time
    in [30, 300] minutes, and allowed delivery statuses.

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
    :return: DataFrame with columns ``log_ref`` (e.g. ``'LIV-42'``) and ``http_status``.
    :rtype: pd.DataFrame
    :raises FileNotFoundError: If ``log_path`` does not exist.

    Example:
        >>> from pathlib import Path
        >>> # Assuming data/raw/access.log exists:
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


def run_iragi_audit(
    raw_dir: Path = Path("data/raw"),
    processed_dir: Path = Path("data/processed"),
    reports_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute end-to-end Iragi profiling, contract quarantine, and reconciliation.

    :param raw_dir: Directory containing ``livraisons.csv`` and ``access.log``.
    :type raw_dir: Path
    :param processed_dir: Directory where ``quarantine_livraisons.csv`` is written.
    :type processed_dir: Path
    :param reports_dir: Optional directory where ``iragi_audit.json`` is saved.
    :type reports_dir: Path | None
    :return: Dictionary of quality scores, drift deltas, DLQ counts, and match rates.
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

    raw_scan = iragi.scan(str(csv_path))
    raw_df = pd.read_csv(csv_path, skip_blank_lines=True)
    normalized_df = _normalize_whitespace_columns(raw_df)

    contract = build_delivery_contract()
    violations = iragi.validate_contract(normalized_df, contract)

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

    clean_df = clean_result.df.copy()
    clean_df["id"] = clean_df["id"].astype(int)
    clean_scan = iragi.scan_dataframe(clean_df)
    drift = iragi.compare_scans(raw_scan, clean_scan)

    outlier_count = int(detect_outliers_modified_zscore(clean_df["temps"].dropna()))

    log_df = extract_log_delivery_refs(log_path)
    reconciliation = iragi.reconcile(
        clean_df,
        log_df,
        on=("id", "log_ref"),
        key_transform=r"(\d+)",
    )

    audit_summary: dict[str, Any] = {
        "iragi_version": iragi.__version__,
        "raw_rows": raw_scan.row_count,
        "raw_quality_score": round(float(raw_scan.quality_score.total_score), 2),
        "clean_rows": clean_scan.row_count,
        "clean_quality_score": round(float(clean_scan.quality_score.total_score), 2),
        "quality_score_delta": round(float(drift.score_delta), 2),
        "duplicates_removed": int(clean_result.changes.get("duplicates_removed", 0)),
        "contract_violations_count": sum(v.failed_count for v in violations),
        "contract_violations": [
            {"column": v.column, "rule": v.rule, "failed_count": v.failed_count}
            for v in violations
        ],
        "quarantined_rows_count": len(clean_result.quarantine_df),
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
