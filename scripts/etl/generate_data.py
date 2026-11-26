"""Random logistics dataset generator with calibrated data quality anomalies.

Generates the three raw files required by the UNIX Systems Final Project:
``livraisons.csv`` (1000-5000 deliveries), ``livreurs.json`` (20-50 couriers),
and ``access.log`` (500-2000 Apache HTTP access records). Controlled anomalies
(duplicates, blank lines, whitespace padding, missing fields, and out-of-bounds
metrics) are injected so downstream UNIX pipelines and ``iragi`` contracts can
measure exact remediation gains.

Example:
    Run from the command line to populate ``data/raw/``::

        $ python3 -m scripts.etl.generate_data
"""

from __future__ import annotations

import csv
import io
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

CITIES: tuple[str, ...] = (
    "Paris",
    "Lyon",
    "Marseille",
    "Lille",
    "Bordeaux",
    "Toulouse",
    "Nantes",
    "Nice",
    "Strasbourg",
)

STATUSES: tuple[str, ...] = ("livre", "en_cours", "retarde", "annule")
STATUS_WEIGHTS: tuple[int, ...] = (68, 14, 12, 6)
VEHICLES: tuple[str, ...] = ("Velo", "Moto", "Camionnette", "Fourgon")

FIRST_NAMES: tuple[str, ...] = (
    "Jean",
    "Marie",
    "Patrick",
    "Amina",
    "Luc",
    "Sarah",
    "David",
    "Chantal",
    "Eric",
    "Nadia",
    "Hugo",
    "grace",
)

LAST_NAMES: tuple[str, ...] = (
    "Mukala",
    "Kabongo",
    "Martin",
    "Bernard",
    "Dubois",
    "Ilunga",
    "Moreau",
    "Kasongo",
    "Laurent",
    "Petit",
)


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration parameters controlling synthetic dataset generation.

    :param output_dir: Target directory where raw files are written.
    :type output_dir: Path
    :param deliveries_count: Number of clean base rows in ``livraisons.csv`` (1000-5000).
    :type deliveries_count: int
    :param couriers_count: Number of courier profiles in ``livreurs.json`` (20-50).
    :type couriers_count: int
    :param access_logs_count: Number of HTTP lines in ``access.log`` (500-2000).
    :type access_logs_count: int
    :param seed: Random seed for reproducible generation.
    :type seed: int

    Example:
        >>> from pathlib import Path
        >>> cfg = DatasetConfig(output_dir=Path("data/raw"), deliveries_count=1500)
        >>> cfg.deliveries_count
        1500
    """

    output_dir: Path = Path("data/raw")
    deliveries_count: int = 2500
    couriers_count: int = 35
    access_logs_count: int = 1200
    seed: int = 2026


def generate_couriers(rng: random.Random, count: int) -> list[dict[str, Any]]:
    """Generate courier records matching the ``livreurs.json`` specification.

    :param rng: Seeded random number generator instance.
    :type rng: random.Random
    :param count: Number of couriers to generate (20-50).
    :type count: int
    :return: List of courier dictionaries ready for JSON serialization.
    :rtype: list[dict[str, Any]]
    :raises ValueError: If ``count`` is outside the [20, 50] exam interval.

    Example:
        >>> import random
        >>> couriers = generate_couriers(random.Random(1), 20)
        >>> len(couriers)
        20
    """
    if not 20 <= count <= 50:
        raise ValueError(f"couriers_count must be between 20 and 50, got {count}")

    couriers: list[dict[str, Any]] = []
    for courier_id in range(1, count + 1):
        full_name = f"{rng.choice(FIRST_NAMES).capitalize()} {rng.choice(LAST_NAMES)}"
        couriers.append(
            {
                "id": courier_id,
                "nom": full_name,
                "ville": rng.choice(CITIES),
                "experience": rng.randint(0, 30),
                "note": round(rng.uniform(2.5, 5.0), 2),
                "vehicule": rng.choice(VEHICLES),
            }
        )
    return couriers


def generate_deliveries_csv(
    rng: random.Random, count: int, target_path: Path
) -> dict[str, int]:
    """Generate ``livraisons.csv`` with base valid rows and calibrated anomalies.

    Injects exact duplicates, whitespace-padded cells, blank lines, missing values,
    and out-of-range metrics so Phase 2 UNIX cleaning and ``iragi`` DataContracts
    have concrete anomalies to remediate and quarantine.

    :param rng: Seeded random number generator instance.
    :type rng: random.Random
    :param count: Number of clean base delivery rows (1000-5000).
    :type count: int
    :param target_path: Destination file path for ``livraisons.csv``.
    :type target_path: Path
    :return: Dictionary summarizing base rows and injected anomaly counts.
    :rtype: dict[str, int]
    :raises ValueError: If ``count`` is outside the [1000, 5000] exam interval.

    Example:
        >>> import random
        >>> from pathlib import Path
        >>> stats = generate_deliveries_csv(random.Random(1), 1000, Path("/tmp/livraisons.csv"))
        >>> stats["deliveries_base_rows"]
        1000
    """
    if not 1000 <= count <= 5000:
        raise ValueError(f"deliveries_count must be between 1000 and 5000, got {count}")

    start_date = date(2026, 9, 1)
    base_rows: list[list[str]] = []

    for delivery_id in range(1, count + 1):
        delivery_date = start_date + timedelta(days=rng.randint(0, 89))
        city = rng.choice(CITIES)
        weight = f"{rng.uniform(5.0, 50.0):.2f}"
        distance = rng.randint(10, 500)
        # Correlate delivery duration loosely with distance while staying in [30, 300]
        duration = min(300, max(30, int(25 + distance * rng.uniform(0.35, 0.55))))
        status = rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        base_rows.append(
            [
                str(delivery_id),
                delivery_date.isoformat(),
                city,
                weight,
                str(distance),
                str(duration),
                status,
            ]
        )

    # Build dirty rows: duplicates, whitespace padding, missing values, contract outliers
    duplicates = [list(row) for row in rng.sample(base_rows, k=20)]
    whitespace_rows = [
        [
            f"{count + idx + 1}",
            f" {start_date.isoformat()} ",
            f"  {rng.choice(CITIES)}  ",
            "18.50",
            "120",
            "95",
            " livre ",
        ]
        for idx in range(8)
    ]
    invalid_rows = [
        [f"{count + 101}", "2026-13-45", "Paris", "12.40", "100", "80", "livre"],
        [f"{count + 102}", "2026-10-12", "Lyon", "-4.50", "85", "60", "livre"],
        [f"{count + 103}", "2026-10-15", "Marseille", "75.00", "140", "110", "retarde"],
        [f"{count + 104}", "2026-10-18", "Lille", "15.00", "820", "490", "retarde"],
        [f"{count + 105}", "2026-10-20", "", "22.10", "60", "55", "en_cours"],
        [f"{count + 106}", "2026-10-22", "Nantes", "19.00", "90", "", "livre"],
        [f"{count + 107}", "2026-10-25", "Nice", "14.20", "70", "65", "inconnu"],
        ["", "2026-10-28", "Bordeaux", "11.00", "45", "40", "annule"],
    ]

    all_rows = base_rows + duplicates + whitespace_rows + invalid_rows
    rng.shuffle(all_rows)

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["id", "date", "ville", "poids", "distance", "temps", "statut"])
    blank_lines_injected = 0
    for idx, row in enumerate(all_rows):
        writer.writerow(row)
        if idx in {25, 150, 400, 750, 980}:
            buffer.write("\n")
            blank_lines_injected += 1

    target_path.write_text(buffer.getvalue(), encoding="utf-8")
    return {
        "deliveries_base_rows": count,
        "injected_duplicates": len(duplicates),
        "injected_whitespace_rows": len(whitespace_rows),
        "injected_invalid_rows": len(invalid_rows),
        "injected_blank_lines": blank_lines_injected,
    }


def generate_access_logs(
    rng: random.Random, count: int, max_delivery_id: int, target_path: Path
) -> int:
    """Generate Apache Combined/Common format HTTP logs referencing deliveries.

    Includes valid ``/api/livraisons/LIV-<id>`` endpoints plus a small fraction
    of orphan delivery references (IDs above ``max_delivery_id``) to support
    cross-source reconciliation testing with ``iragi.reconcile``.

    :param rng: Seeded random number generator instance.
    :type rng: random.Random
    :param count: Number of log lines to write (500-2000).
    :type count: int
    :param max_delivery_id: Maximum valid delivery identifier from ``livraisons.csv``.
    :type max_delivery_id: int
    :param target_path: Destination path for ``access.log``.
    :type target_path: Path
    :return: Total number of log lines written.
    :rtype: int
    :raises ValueError: If ``count`` is outside the [500, 2000] exam interval.

    Example:
        >>> import random
        >>> from pathlib import Path
        >>> written = generate_access_logs(random.Random(1), 500, 1000, Path("/tmp/access.log"))
        >>> written
        500
    """
    if not 500 <= count <= 2000:
        raise ValueError(
            f"access_logs_count must be between 500 and 2000, got {count}"
        )

    methods = ("GET", "POST", "PUT", "DELETE")
    method_weights = (70, 15, 12, 3)
    statuses = (200, 201, 400, 404, 500)
    status_weights = (78, 8, 5, 6, 3)
    months = ("Sep", "Oct", "Nov")

    lines: list[str] = []
    for idx in range(count):
        ip = f"192.168.{rng.randint(1, 20)}.{rng.randint(2, 254)}"
        day = rng.randint(1, 28)
        month = rng.choice(months)
        hour = rng.randint(6, 22)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        timestamp = f"{day:02d}/{month}/2026:{hour:02d}:{minute:02d}:{second:02d} +0200"
        method = rng.choices(methods, weights=method_weights, k=1)[0]

        if idx == 0 or rng.random() < 0.85:
            ref_id = rng.randint(1, max_delivery_id)
            url = f"/api/livraisons/LIV-{ref_id}"
            http_status = rng.choices(statuses, weights=status_weights, k=1)[0]
        elif rng.random() < 0.5:
            orphan_id = max_delivery_id + rng.randint(500, 900)
            url = f"/api/livraisons/LIV-{orphan_id}"
            http_status = 404
        else:
            url = rng.choice(("/api/livreurs", "/health", "/api/stats/summary"))
            http_status = 200

        payload_bytes = rng.randint(128, 16384)
        lines.append(
            f'{ip} - - [{timestamp}] "{method} {url} HTTP/1.1" {http_status} {payload_bytes}'
        )

    target_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def generate_all_datasets(config: DatasetConfig | None = None) -> dict[str, Any]:
    """Generate ``livraisons.csv``, ``livreurs.json``, and ``access.log`` in one run.

    :param config: Optional dataset configuration; defaults to :class:`DatasetConfig`.
    :type config: DatasetConfig | None
    :return: Generation manifest detailing row counts, anomalies, and file paths.
    :rtype: dict[str, Any]

    Example:
        >>> from pathlib import Path
        >>> cfg = DatasetConfig(output_dir=Path("/tmp/raw_demo"), deliveries_count=1000)
        >>> manifest = generate_all_datasets(cfg)
        >>> manifest["couriers_count"]
        35
    """
    cfg = config or DatasetConfig()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg.seed)

    couriers = generate_couriers(rng, cfg.couriers_count)
    couriers_path = cfg.output_dir / "livreurs.json"
    couriers_path.write_text(
        json.dumps(couriers, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    deliveries_path = cfg.output_dir / "livraisons.csv"
    delivery_stats = generate_deliveries_csv(rng, cfg.deliveries_count, deliveries_path)

    logs_path = cfg.output_dir / "access.log"
    logs_written = generate_access_logs(
        rng, cfg.access_logs_count, cfg.deliveries_count, logs_path
    )

    manifest: dict[str, Any] = {
        "seed": cfg.seed,
        "couriers_count": len(couriers),
        "access_logs_count": logs_written,
        **delivery_stats,
    }
    manifest_path = cfg.output_dir / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    summary = generate_all_datasets()
    print(json.dumps(summary, indent=2))
