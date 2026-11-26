"""Automated Metabase provisioning and dashboard creation via Traefik REST API.

Connects Metabase to the live PostgreSQL ``logistics_db`` container and creates
native SQL cards plus an operational logistics dashboard covering city volumes,
delay rates, monthly evolution, status breakdown, vehicle comparison, courier
performance, and Apache HTTP anomalies.

Example:
    Provision Metabase and create the dashboard::

        $ .venv/bin/python3 -m scripts.reporting.setup_metabase
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _api_request(
    base_url: str,
    host_header: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    session_token: str | None = None,
) -> dict[str, Any]:
    """Execute an HTTP JSON request against Metabase routed through Traefik.

    :param base_url: Traefik HTTP entrypoint URL (e.g. ``http://127.0.0.1:8080``).
    :type base_url: str
    :param host_header: Virtual host header routed to Metabase.
    :type host_header: str
    :param path: API path starting with ``/api/...``.
    :type path: str
    :param method: HTTP method name.
    :type method: str
    :param payload: Optional JSON body dictionary.
    :type payload: dict[str, Any] | None
    :param session_token: Optional Metabase session ID token.
    :type session_token: str | None
    :return: Parsed JSON response dictionary.
    :rtype: dict[str, Any]

    Example:
        >>> # props = _api_request("http://127.0.0.1:8080", "metabase.localhost", "/api/session/properties")
    """
    headers: dict[str, str] = {
        "Host": host_header,
        "Content-Type": "application/json",
    }
    if session_token:
        headers["X-Metabase-Session"] = session_token

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def provision_metabase_dashboard(
    base_url: str = "http://127.0.0.1:8080",
    host_header: str = "metabase.localhost",
    admin_email: str = "eric.lutumba@unilu.ac.cd",
    admin_password: str = "UnixPipeline2026!",
    output_manifest: Path = Path("data/reports/metabase_dashboard.json"),
) -> dict[str, Any]:
    """Configure Metabase admin, PostgreSQL datasource, SQL questions, and dashboard.

    :param base_url: Traefik URL reaching Metabase.
    :type base_url: str
    :param host_header: Traefik router Host header.
    :type host_header: str
    :param admin_email: Initial Metabase administrator email.
    :type admin_email: str
    :param admin_password: Initial Metabase administrator password.
    :type admin_password: str
    :param output_manifest: Destination JSON path recording dashboard metadata.
    :type output_manifest: Path
    :return: Dictionary containing database ID, dashboard ID, and card IDs.
    :rtype: dict[str, Any]

    Example:
        >>> # summary = provision_metabase_dashboard()
    """
    props = _api_request(base_url, host_header, "/api/session/properties")
    pg_user = os.environ.get("POSTGRES_USER", "logistics")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "logistics_pass")
    pg_db = os.environ.get("POSTGRES_DB", "logistics_db")

    if not props.get("has-user-setup"):
        setup_payload = {
            "token": props["setup-token"],
            "user": {
                "first_name": "Eric",
                "last_name": "Lutumba Miteo",
                "email": admin_email,
                "password": admin_password,
                "site_name": "UNIX Logistics Analytics",
            },
            "prefs": {
                "site_name": "UNIX Logistics Analytics",
                "site_locale": "fr",
                "allow_tracking": False,
            },
            "database": {
                "engine": "postgres",
                "name": "Logistics PostgreSQL",
                "details": {
                    "host": "db",
                    "port": 5432,
                    "dbname": pg_db,
                    "user": pg_user,
                    "password": pg_pass,
                    "ssl": False,
                },
            },
        }
        setup_res = _api_request(
            base_url, host_header, "/api/setup", method="POST", payload=setup_payload
        )
        session_id = setup_res["id"]
    else:
        login_res = _api_request(
            base_url,
            host_header,
            "/api/session",
            method="POST",
            payload={"username": admin_email, "password": admin_password},
        )
        session_id = login_res["id"]

    dbs = _api_request(
        base_url, host_header, "/api/database", session_token=session_id
    )
    db_list = dbs.get("data", dbs) if isinstance(dbs, dict) else dbs
    pg_entry = next(
        (d for d in db_list if d.get("engine") == "postgres"),
        None,
    )
    if pg_entry is None:
        created_db = _api_request(
            base_url,
            host_header,
            "/api/database",
            method="POST",
            session_token=session_id,
            payload={
                "engine": "postgres",
                "name": "Logistics PostgreSQL",
                "details": {
                    "host": "db",
                    "port": 5432,
                    "dbname": pg_db,
                    "user": pg_user,
                    "password": pg_pass,
                    "ssl": False,
                },
            },
        )
        db_id = int(created_db["id"])
    else:
        db_id = int(pg_entry["id"])

    _api_request(
        base_url,
        host_header,
        f"/api/database/{db_id}/sync_schema",
        method="POST",
        session_token=session_id,
    )

    dash = _api_request(
        base_url,
        host_header,
        "/api/dashboard",
        method="POST",
        session_token=session_id,
        payload={
            "name": "Analyse Logistique - Pipeline UNIX",
            "description": "Tableau de bord connecte a PostgreSQL (livraisons, livreurs, logs Apache).",
        },
    )
    dash_id = int(dash["id"])

    questions = [
        (
            "Livraisons et Retard par Ville",
            "bar",
            "SELECT ville, COUNT(*) AS total_livraisons, ROUND(100.0 * SUM(CASE WHEN statut = 'retarde' THEN 1 ELSE 0 END) / COUNT(*), 2) AS taux_retard_pct FROM deliveries GROUP BY ville ORDER BY total_livraisons DESC;",
            {"row": 0, "col": 0, "size_x": 12, "size_y": 6},
        ),
        (
            "Evolution Mensuelle des Livraisons",
            "bar",
            "SELECT TO_CHAR(DATE_TRUNC('month', delivery_date), 'YYYY-MM') AS mois, COUNT(*) AS total_livraisons, SUM(CASE WHEN statut = 'retarde' THEN 1 ELSE 0 END) AS retardees FROM deliveries GROUP BY mois ORDER BY mois;",
            {"row": 0, "col": 12, "size_x": 12, "size_y": 6},
        ),
        (
            "Repartition des Statuts",
            "pie",
            "SELECT statut, COUNT(*) AS total FROM deliveries GROUP BY statut ORDER BY total DESC;",
            {"row": 6, "col": 0, "size_x": 8, "size_y": 6},
        ),
        (
            "Comparaison par Type de Vehicule",
            "table",
            "SELECT type_vehicule, COUNT(*) AS livraisons, ROUND(AVG(distance), 2) AS dist_moy_km, ROUND(AVG(temps), 2) AS duree_moy_min, ROUND(AVG(cout_livraison), 2) AS cout_moy_eur FROM deliveries GROUP BY type_vehicule ORDER BY livraisons DESC;",
            {"row": 6, "col": 8, "size_x": 16, "size_y": 6},
        ),
        (
            "Performance des Livreurs",
            "table",
            "SELECT c.nom, c.ville, c.experience, c.note, COUNT(d.id) AS livraisons_gerees FROM couriers c LEFT JOIN deliveries d ON d.livreur_id = c.id GROUP BY c.id, c.nom, c.ville, c.experience, c.note ORDER BY livraisons_gerees DESC LIMIT 15;",
            {"row": 12, "col": 0, "size_x": 14, "size_y": 6},
        ),
        (
            "Anomalies HTTP Apache (access.log)",
            "bar",
            "SELECT http_status::TEXT AS code_http, COUNT(*) AS requetes FROM web_access_logs GROUP BY http_status ORDER BY requetes DESC;",
            {"row": 12, "col": 14, "size_x": 10, "size_y": 6},
        ),
    ]

    dashcards = []
    created_cards = []
    for idx, (title, display, sql_text, layout) in enumerate(questions, start=1):
        card = _api_request(
            base_url,
            host_header,
            "/api/card",
            method="POST",
            session_token=session_id,
            payload={
                "name": title,
                "display": display,
                "visualization_settings": {},
                "dataset_query": {
                    "type": "native",
                    "database": db_id,
                    "native": {"query": sql_text},
                },
            },
        )
        card_id = int(card["id"])
        created_cards.append({"id": card_id, "name": title, "display": display})
        dashcards.append({"id": -idx, "card_id": card_id, **layout})

    _api_request(
        base_url,
        host_header,
        f"/api/dashboard/{dash_id}",
        method="PUT",
        session_token=session_id,
        payload={"dashcards": dashcards},
    )

    result = {
        "metabase_url": f"http://{host_header}:8080/dashboard/{dash_id}",
        "admin_email": admin_email,
        "database_id": db_id,
        "dashboard_id": dash_id,
        "cards": created_cards,
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    summary = provision_metabase_dashboard()
    print(json.dumps(summary, indent=2))
