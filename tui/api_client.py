"""HTTP client for the BitCraft FastAPI backend.

All ML results are pre-computed; this client only reads cached alert,
graph, and community data, it never triggers scoring (plan section 10.3).
"""

import httpx

BASE_URL = "http://localhost:8000"


def get_alerts(params: dict | None = None) -> list[dict]:
    """GET /alerts: paginated, filterable ranked alert list."""
    raise NotImplementedError


def get_alert_detail(tx_id: int) -> dict:
    """GET /alerts/{tx_id}: full detail, scores, SHAP, evidence, coverage flags."""
    raise NotImplementedError


def get_graph(tx_id: int, depth: int = 1) -> dict:
    """GET /graph/{tx_id}: subgraph around one transaction."""
    raise NotImplementedError


def get_community(community_id: int) -> dict:
    """GET /communities/{community_id}: members, size, illicit ratio."""
    raise NotImplementedError


def get_stats_summary() -> dict:
    """GET /stats/summary: dashboard KPIs."""
    raise NotImplementedError


def get_pipeline_status() -> dict:
    """GET /pipeline/status: last/running ML pipeline job status."""
    raise NotImplementedError
