"""Dual-mode realistic synthetic logistics dataset generator (EXAM and EXTENDED modes).

Supports two independent simulation configurations:
- ``exam`` (default): Strictly enforces the professor's exam bounds
  (1,000-5,000 deliveries, 20-50 couriers, 500-2,000 Apache HTTP logs,
  9 French cities, 3-month window).
- ``extended``: Stress-testing configuration targeting 12,000 deliveries per
  month per city by default (108,000/month across 9 cities) with configurable
  city market coefficients, seasonality, weekday patterns, and peak periods.
  All coefficients are explicit simulation hypotheses, never official statistics.

Example:
    Generate EXAM mode datasets from CLI::

        $ python3 -m scripts.etl.generate_data --mode exam

    Generate EXTENDED mode datasets from CLI::

        $ python3 -m scripts.etl.generate_data --mode extended --months 3
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
from dataclasses import dataclass, field
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

# Simulation hypotheses only (not official statistics):
# relative market weight, urban share, base delay probability, average distance factor.
DEFAULT_CITY_COEFFICIENTS: dict[str, dict[str, float]] = {
    "Paris": {"market": 1.35, "urban_share": 0.72, "delay_prob": 0.14, "dist_factor": 0.85},
    "Lyon": {"market": 1.15, "urban_share": 0.58, "delay_prob": 0.11, "dist_factor": 1.00},
    "Marseille": {"market": 1.10, "urban_share": 0.55, "delay_prob": 0.13, "dist_factor": 1.05},
    "Lille": {"market": 0.95, "urban_share": 0.52, "delay_prob": 0.12, "dist_factor": 1.02},
    "Bordeaux": {"market": 0.92, "urban_share": 0.48, "delay_prob": 0.09, "dist_factor": 1.08},
    "Toulouse": {"market": 0.96, "urban_share": 0.50, "delay_prob": 0.10, "dist_factor": 1.04},
    "Nantes": {"market": 0.88, "urban_share": 0.49, "delay_prob": 0.08, "dist_factor": 0.98},
    "Nice": {"market": 0.84, "urban_share": 0.60, "delay_prob": 0.13, "dist_factor": 0.95},
    "Strasbourg": {"market": 0.85, "urban_share": 0.47, "delay_prob": 0.09, "dist_factor": 1.06},
}

STATUSES: tuple[str, ...] = ("livre", "en_cours", "retarde", "annule")
VEHICLES: tuple[str, ...] = ("Velo", "Moto", "Camionnette", "Fourgon")
COURIER_STATUSES: tuple[str, ...] = ("actif", "actif", "actif", "en_conge")
DELIVERY_TYPES: tuple[str, ...] = ("standard", "express")
CLIENT_TYPES: tuple[str, ...] = ("particulier", "entreprise")

VEHICLE_PROFILES: dict[str, dict[str, float]] = {
    "Velo": {"max_weight": 15.0, "speed_kmh": 18.0, "base_cost": 4.5},
    "Moto": {"max_weight": 25.0, "speed_kmh": 42.0, "base_cost": 7.0},
    "Camionnette": {"max_weight": 42.0, "speed_kmh": 68.0, "base_cost": 12.0},
    "Fourgon": {"max_weight": 50.0, "speed_kmh": 78.0, "base_cost": 16.5},
}

FIRST_NAMES: tuple[str, ...] = (
    "Jean",
    "Marie",
    "Luc",
    "Sophie",
    "Thomas",
    "Camille",
    "Nicolas",
    "Laura",
    "Antoine",
    "Claire",
    "Julien",
    "Emma",
)

LAST_NAMES: tuple[str, ...] = (
    "Martin",
    "Bernard",
    "Dubois",
    "Thomas",
    "Robert",
    "Richard",
    "Petit",
    "Durand",
    "Leroy",
    "Moreau",
    "Simon",
    "Laurent",
)

DELIVERY_CSV_HEADER: list[str] = [
    "id",
    "date",
    "ville",
    "livreur_id",
    "poids",
    "distance",
    "temps",
    "temps_prevu",
    "statut",
    "type_livraison",
    "type_client",
    "type_vehicule",
    "cout_livraison",
    "zone_livraison",
]


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration parameters controlling EXAM or EXTENDED dataset generation.

    :param mode: Generation mode (``'exam'`` or ``'extended'``).
    :type mode: str
    :param output_dir: Target directory where raw files are written.
    :type output_dir: Path
    :param deliveries_count: Base deliveries in EXAM mode (1000-5000).
    :type deliveries_count: int
    :param deliveries_per_city_month: Target base deliveries/city/month in EXTENDED mode.
    :type deliveries_per_city_month: int
    :param months: Number of months covered (default: 3).
    :type months: int
    :param start_date: Simulation start date (ISO ``YYYY-MM-DD``).
    :type start_date: str
    :param end_date: Optional simulation end date (ISO ``YYYY-MM-DD``).
    :type end_date: str | None
    :param couriers_count: Number of courier profiles in ``livreurs.json`` (20-50 in EXAM).
    :type couriers_count: int
    :param access_logs_count: Number of HTTP lines in ``access.log`` (500-2000 in EXAM).
    :type access_logs_count: int
    :param seed: Random seed for reproducible generation.
    :type seed: int
    :param city_coefficients: Optional per-city simulation hypotheses override.
    :type city_coefficients: dict[str, dict[str, float]]
    :param seasonality_factors: Optional monthly volume multipliers.
    :type seasonality_factors: tuple[float, ...]

    Example:
        >>> from pathlib import Path
        >>> cfg = DatasetConfig(mode="exam", output_dir=Path("data/raw"), deliveries_count=2500)
        >>> cfg.mode
        'exam'
    """

    mode: str = "exam"
    output_dir: Path = Path("data/raw")
    deliveries_count: int = 2500
    deliveries_per_city_month: int = 12000
    months: int = 3
    start_date: str = "2026-09-01"
    end_date: str | None = None
    couriers_count: int = 35
    access_logs_count: int = 1200
    seed: int = 2026
    city_coefficients: dict[str, dict[str, float]] = field(
        default_factory=lambda: dict(DEFAULT_CITY_COEFFICIENTS)
    )
    seasonality_factors: tuple[float, ...] = (0.95, 1.02, 1.08)


def _resolve_date_window(cfg: DatasetConfig) -> tuple[date, date]:
    """Compute inclusive start and end dates from configuration.

    :param cfg: Dataset configuration instance.
    :type cfg: DatasetConfig
    :return: Tuple of ``(start_date, end_date)``.
    :rtype: tuple[date, date]

    Example:
        >>> d1, d2 = _resolve_date_window(DatasetConfig())
        >>> (d2 - d1).days >= 89
        True
    """
    start = date.fromisoformat(cfg.start_date)
    if cfg.end_date:
        return start, date.fromisoformat(cfg.end_date)
    return start, start + timedelta(days=max(29, cfg.months * 30 - 1))


def generate_couriers(
    rng: random.Random, count: int, mode: str = "exam"
) -> list[dict[str, Any]]:
    """Generate realistic courier profiles matching ``livreurs.json`` specifications.

    :param rng: Seeded random number generator instance.
    :type rng: random.Random
    :param count: Number of couriers to generate (20-50 in EXAM mode).
    :type count: int
    :param mode: Generation mode (``'exam'`` or ``'extended'``).
    :type mode: str
    :return: List of courier dictionaries ready for JSON serialization.
    :rtype: list[dict[str, Any]]
    :raises ValueError: If EXAM bounds [20, 50] are violated.

    Example:
        >>> import random
        >>> couriers = generate_couriers(random.Random(1), 25, "exam")
        >>> len(couriers)
        25
    """
    if mode == "exam" and not 20 <= count <= 50:
        raise ValueError(f"EXAM couriers_count must be between 20 and 50, got {count}")

    couriers: list[dict[str, Any]] = []
    for courier_id in range(1, count + 1):
        city = CITIES[(courier_id - 1) % len(CITIES)]
        exp = rng.randint(0, 28)
        base_rating = min(5.0, max(2.2, 3.2 + exp * 0.04 + rng.uniform(-0.7, 0.7)))
        couriers.append(
            {
                "id": courier_id,
                "nom": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                "ville": city,
                "experience": exp,
                "note": round(base_rating, 2),
                "vehicule": rng.choice(VEHICLES),
                "statut": rng.choice(COURIER_STATUSES),
            }
        )
    return couriers


def _pick_vehicle_for_weight(
    rng: random.Random, weight: float, zone: str
) -> str:
    """Select an appropriate vehicle respecting package weight and delivery zone.

    :param rng: Seeded random generator.
    :type rng: random.Random
    :param weight: Package weight in kg.
    :type weight: float
    :param zone: Delivery zone (``'urbaine'`` or ``'interurbaine'``).
    :type zone: str
    :return: Vehicle type name.
    :rtype: str

    Example:
        >>> import random
        >>> _pick_vehicle_for_weight(random.Random(1), 45.0, "interurbaine")
        'Fourgon'
    """
    if zone == "interurbaine":
        return "Fourgon" if weight > 35.0 or rng.random() < 0.45 else "Camionnette"
    if weight <= 15.0 and rng.random() < 0.45:
        return "Velo"
    if weight <= 25.0 and rng.random() < 0.65:
        return "Moto"
    return "Camionnette" if weight <= 40.0 else "Fourgon"


def _compute_city_targets(cfg: DatasetConfig) -> dict[str, int]:
    """Compute per-city base delivery counts using configured variation hypotheses.

    :param cfg: Dataset configuration instance.
    :type cfg: DatasetConfig
    :return: Mapping from city name to target base delivery count.
    :rtype: dict[str, int]

    Example:
        >>> targets = _compute_city_targets(DatasetConfig(mode="exam", deliveries_count=1800))
        >>> sum(targets.values())
        1800
    """
    weights = {c: cfg.city_coefficients[c]["market"] for c in CITIES}
    if cfg.mode == "exam":
        total_weight = sum(weights.values())
        targets = {
            c: max(1, int(round(cfg.deliveries_count * (weights[c] / total_weight))))
            for c in CITIES
        }
        diff = cfg.deliveries_count - sum(targets.values())
        targets["Paris"] += diff
        return targets

    # EXTENDED mode: scale around deliveries_per_city_month * months * market_coeff * seasonality
    avg_season = sum(cfg.seasonality_factors) / len(cfg.seasonality_factors)
    return {
        c: max(
            100,
            int(round(cfg.deliveries_per_city_month * cfg.months * weights[c] * avg_season)),
        )
        for c in CITIES
    }


def generate_deliveries_csv(
    rng: random.Random,
    cfg: DatasetConfig,
    couriers: list[dict[str, Any]],
    target_path: Path,
) -> dict[str, Any]:
    """Generate ``livraisons.csv`` with business-coherent metrics and calibrated anomalies.

    :param rng: Seeded random number generator.
    :type rng: random.Random
    :param cfg: Dataset configuration parameters.
    :type cfg: DatasetConfig
    :param couriers: Generated courier list so ``livreur_id`` references real couriers.
    :type couriers: list[dict[str, Any]]
    :param target_path: Destination CSV path.
    :type target_path: Path
    :return: Dictionary summarizing generated counts and injected anomalies.
    :rtype: dict[str, Any]
    :raises ValueError: If EXAM delivery count is outside [1000, 5000].

    Example:
        >>> import random
        >>> from pathlib import Path
        >>> c = generate_couriers(random.Random(1), 25, "exam")
        >>> res = generate_deliveries_csv(random.Random(1), DatasetConfig(deliveries_count=1200), c, Path("/tmp/l.csv"))
        >>> res["deliveries_base_rows"]
        1200
    """
    if cfg.mode == "exam" and not 1000 <= cfg.deliveries_count <= 5000:
        raise ValueError(
            f"EXAM deliveries_count must be between 1000 and 5000, got {cfg.deliveries_count}"
        )

    couriers_by_city: dict[str, list[int]] = {c: [] for c in CITIES}
    for courier in couriers:
        couriers_by_city[courier["ville"]].append(int(courier["id"]))
    all_courier_ids = [int(c["id"]) for c in couriers]

    start_dt, end_dt = _resolve_date_window(cfg)
    span_days = max(1, (end_dt - start_dt).days)
    city_targets = _compute_city_targets(cfg)

    # Pre-build weighted day offsets (weekday + peak month simulation)
    day_pool: list[int] = []
    for offset in range(span_days + 1):
        d = start_dt + timedelta(days=offset)
        month_idx = min(len(cfg.seasonality_factors) - 1, offset // 30)
        mult = cfg.seasonality_factors[month_idx]
        # Higher commercial volume Tuesday-Friday, lower Sunday
        weekday_mult = 1.25 if d.weekday() in (1, 2, 3, 4) else (0.65 if d.weekday() == 6 else 1.0)
        day_pool.extend([offset] * max(1, int(round(4 * mult * weekday_mult))))

    rows: list[list[str]] = []
    delivery_id = 1
    for city in CITIES:
        coeff = cfg.city_coefficients[city]
        city_couriers = couriers_by_city[city] or all_courier_ids
        urban_prob = coeff["urban_share"]
        delay_prob = coeff["delay_prob"]
        dist_factor = coeff["dist_factor"]

        for _ in range(city_targets[city]):
            day_offset = rng.choice(day_pool)
            deliv_date = (start_dt + timedelta(days=day_offset)).isoformat()
            zone = "urbaine" if rng.random() < urban_prob else "interurbaine"
            deliv_type = "express" if rng.random() < 0.28 else "standard"
            client_type = "entreprise" if rng.random() < 0.42 else "particulier"

            weight = round(rng.uniform(5.0, 50.0), 2)
            vehicle = _pick_vehicle_for_weight(rng, weight, zone)
            if zone == "urbaine":
                distance = max(10, min(85, int(round(rng.randint(10, 60) * dist_factor))))
            else:
                distance = max(60, min(500, int(round(rng.randint(65, 480) * dist_factor))))

            speed = VEHICLE_PROFILES[vehicle]["speed_kmh"]
            handling_min = 18.0 if deliv_type == "express" else 26.0
            planned_time = min(285, max(30, int(round(handling_min + (distance / speed) * 60.0))))

            roll = rng.random()
            if roll < 0.055:
                status = "annule"
                actual_time = max(30, min(300, planned_time))
            elif roll < 0.055 + delay_prob:
                status = "retarde"
                actual_time = min(300, max(30, int(round(planned_time * rng.uniform(1.15, 1.45)))))
            elif roll < 0.055 + delay_prob + 0.12:
                status = "en_cours"
                actual_time = min(300, max(30, int(round(planned_time * rng.uniform(0.90, 1.08)))))
            else:
                status = "livre"
                actual_time = min(300, max(30, int(round(planned_time * rng.uniform(0.82, 1.05)))))

            base_cost = VEHICLE_PROFILES[vehicle]["base_cost"]
            express_mult = 1.35 if deliv_type == "express" else 1.0
            cost = round((base_cost + weight * 0.45 + distance * 0.12) * express_mult, 2)

            rows.append(
                [
                    str(delivery_id),
                    deliv_date,
                    city,
                    str(rng.choice(city_couriers)),
                    f"{weight:.2f}",
                    str(distance),
                    str(actual_time),
                    str(planned_time),
                    status,
                    deliv_type,
                    client_type,
                    vehicle,
                    f"{cost:.2f}",
                    zone,
                ]
            )
            delivery_id += 1

    base_count = len(rows)
    dup_count = 35 if cfg.mode == "exam" else max(120, base_count // 500)
    duplicates = [list(r) for r in rng.sample(rows, k=dup_count)]

    whitespace_rows = [
        [
            str(delivery_id + idx),
            f" {(start_dt + timedelta(days=idx * 2)).isoformat()} ",
            f"  {CITIES[idx % len(CITIES)]}  ",
            str(couriers[idx % len(couriers)]["id"]),
            "18.50",
            "95",
            "82",
            "80",
            " livre ",
            "standard",
            "particulier",
            "Camionnette",
            "31.73",
            "interurbaine",
        ]
        for idx in range(10)
    ]

    bad_id = delivery_id + 100
    invalid_rows = [
        [str(bad_id), "2026-13-45", "Paris", "1", "12.40", "100", "80", "75", "livre", "standard", "particulier", "Camionnette", "28.00", "interurbaine"],
        [str(bad_id + 1), "2026-10-12", "Lyon", "2", "-4.50", "85", "60", "55", "livre", "standard", "entreprise", "Moto", "20.00", "interurbaine"],
        [str(bad_id + 2), "2026-10-15", "Marseille", "3", "75.00", "140", "110", "95", "retarde", "express", "entreprise", "Fourgon", "65.00", "interurbaine"],
        [str(bad_id + 3), "2026-10-18", "Lille", "4", "15.00", "820", "490", "320", "retarde", "standard", "entreprise", "Fourgon", "98.00", "interurbaine"],
        [str(bad_id + 4), "2026-10-20", "", "5", "22.10", "60", "55", "50", "en_cours", "standard", "particulier", "Camionnette", "29.00", "urbaine"],
        [str(bad_id + 5), "2026-10-22", "Nantes", "6", "19.00", "90", "", "70", "livre", "standard", "particulier", "Camionnette", "31.00", "interurbaine"],
        [str(bad_id + 6), "2026-10-25", "Nice", "7", "14.20", "70", "65", "60", "inconnu", "express", "entreprise", "Moto", "25.00", "urbaine"],
        ["", "2026-10-28", "Bordeaux", "8", "11.00", "45", "40", "40", "annule", "standard", "particulier", "Velo", "14.00", "urbaine"],
        [str(bad_id + 7), "2026-11-02", "Strasbourg", "9", "24.00", "640", "420", "290", "retarde", "express", "entreprise", "Fourgon", "89.00", "interurbaine"],
        [str(bad_id + 8), "2026-11-05", "Toulouse", "10", "-1.20", "55", "48", "45", "livre", "standard", "particulier", "Moto", "18.00", "urbaine"],
    ]

    all_rows = rows + duplicates + whitespace_rows + invalid_rows
    rng.shuffle(all_rows)

    blank_positions = {25, 140, 320, 580, 810, 950}
    blank_lines_injected = 0
    with target_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(DELIVERY_CSV_HEADER)
        for idx, row in enumerate(all_rows):
            writer.writerow(row)
            if idx in blank_positions:
                handle.write("\n")
                blank_lines_injected += 1

    return {
        "deliveries_base_rows": base_count,
        "city_base_counts": city_targets,
        "injected_duplicates": len(duplicates),
        "injected_whitespace_rows": len(whitespace_rows),
        "injected_invalid_rows": len(invalid_rows),
        "injected_blank_lines": blank_lines_injected,
    }


def generate_access_logs(
    rng: random.Random,
    count: int,
    max_delivery_id: int,
    max_courier_id: int,
    target_path: Path,
    mode: str = "exam",
) -> int:
    """Generate realistic Apache HTTP logs covering GET/POST and 2xx/4xx/5xx codes.

    :param rng: Seeded random number generator instance.
    :type rng: random.Random
    :param count: Number of log lines to write (500-2000 in EXAM mode).
    :type count: int
    :param max_delivery_id: Maximum valid delivery identifier.
    :type max_delivery_id: int
    :param max_courier_id: Maximum valid courier identifier.
    :type max_courier_id: int
    :param target_path: Destination path for ``access.log``.
    :type target_path: Path
    :param mode: Generation mode (``'exam'`` or ``'extended'``).
    :type mode: str
    :return: Total number of log lines written.
    :rtype: int
    :raises ValueError: If EXAM log count is outside [500, 2000].

    Example:
        >>> import random
        >>> from pathlib import Path
        >>> written = generate_access_logs(random.Random(1), 500, 1000, 30, Path("/tmp/access.log"))
        >>> written
        500
    """
    if mode == "exam" and not 500 <= count <= 2000:
        raise ValueError(
            f"EXAM access_logs_count must be between 500 and 2000, got {count}"
        )

    methods = ("GET", "POST")
    method_weights = (74, 26)
    statuses = (200, 201, 400, 401, 403, 404, 500)
    status_weights = (64, 12, 5, 4, 3, 8, 4)
    months = ("Sep", "Oct", "Nov")

    with target_path.open("w", encoding="utf-8") as handle:
        for idx in range(count):
            ip = f"10.24.{rng.randint(1, 30)}.{rng.randint(2, 254)}"
            day = rng.randint(1, 28)
            month = rng.choice(months)
            hour = rng.randint(6, 22)
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            timestamp = f"{day:02d}/{month}/2026:{hour:02d}:{minute:02d}:{second:02d} +0200"
            method = rng.choices(methods, weights=method_weights, k=1)[0]

            if idx == 0 or rng.random() < 0.72:
                ref_id = rng.randint(1, max_delivery_id)
                url = f"/api/livraisons/LIV-{ref_id}"
                http_status = rng.choices(statuses, weights=status_weights, k=1)[0]
                if method == "POST" and http_status == 200:
                    http_status = 201
            elif rng.random() < 0.45:
                orphan_id = max_delivery_id + rng.randint(5000, 9000)
                url = f"/api/livraisons/LIV-{orphan_id}"
                http_status = 404
            else:
                url = rng.choice(
                    (
                        f"/api/livreurs/{rng.randint(1, max_courier_id)}",
                        "/api/auth/token",
                        "/api/reports/export",
                        "/api/livraisons",
                    )
                )
                http_status = rng.choices((200, 401, 403, 500), weights=(70, 12, 8, 10), k=1)[0]

            payload_bytes = rng.randint(180, 24576)
            handle.write(
                f'{ip} - - [{timestamp}] "{method} {url} HTTP/1.1" {http_status} {payload_bytes}\n'
            )

    return count


def generate_all_datasets(config: DatasetConfig | None = None) -> dict[str, Any]:
    """Generate ``livraisons.csv``, ``livreurs.json``, and ``access.log`` in one run.

    :param config: Optional dataset configuration; defaults to EXAM :class:`DatasetConfig`.
    :type config: DatasetConfig | None
    :return: Generation manifest detailing mode, row counts, anomalies, and file paths.
    :rtype: dict[str, Any]

    Example:
        >>> from pathlib import Path
        >>> cfg = DatasetConfig(mode="exam", output_dir=Path("/tmp/raw_exam"), deliveries_count=1200)
        >>> manifest = generate_all_datasets(cfg)
        >>> manifest["mode"]
        'exam'
    """
    cfg = config or DatasetConfig()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg.seed)

    couriers = generate_couriers(rng, cfg.couriers_count, mode=cfg.mode)
    couriers_path = cfg.output_dir / "livreurs.json"
    couriers_path.write_text(
        json.dumps(couriers, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    deliveries_path = cfg.output_dir / "livraisons.csv"
    delivery_stats = generate_deliveries_csv(rng, cfg, couriers, deliveries_path)

    logs_count = cfg.access_logs_count if cfg.mode == "exam" else max(cfg.access_logs_count, 5000)
    logs_path = cfg.output_dir / "access.log"
    logs_written = generate_access_logs(
        rng,
        logs_count,
        delivery_stats["deliveries_base_rows"],
        len(couriers),
        logs_path,
        mode=cfg.mode,
    )

    start_dt, end_dt = _resolve_date_window(cfg)
    manifest: dict[str, Any] = {
        "mode": cfg.mode,
        "seed": cfg.seed,
        "months": cfg.months,
        "start_date": start_dt.isoformat(),
        "end_date": end_dt.isoformat(),
        "couriers_count": len(couriers),
        "access_logs_count": logs_written,
        "simulation_disclaimer": "Synthetic data with configurable simulation coefficients; not official statistics.",
        **delivery_stats,
    }
    manifest_path = cfg.output_dir / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for EXAM and EXTENDED synthetic data generation."""
    parser = argparse.ArgumentParser(description="Generate synthetic logistics datasets.")
    parser.add_argument("--mode", choices=("exam", "extended"), default="exam")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--deliveries-count", type=int, default=2500)
    parser.add_argument("--per-city-month", type=int, default=12000)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--start-date", type=str, default="2026-09-01")
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--couriers-count", type=int, default=35)
    parser.add_argument("--access-logs-count", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    cfg = DatasetConfig(
        mode=args.mode,
        output_dir=args.output_dir,
        deliveries_count=args.deliveries_count,
        deliveries_per_city_month=args.per_city_month,
        months=args.months,
        start_date=args.start_date,
        end_date=args.end_date,
        couriers_count=args.couriers_count,
        access_logs_count=args.access_logs_count,
        seed=args.seed,
    )
    summary = generate_all_datasets(cfg)
    print(json.dumps(summary, indent=2))
