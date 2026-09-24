"""HTTP client for the BitCraft FastAPI backend.

Thin transport only: JSON in and out. Parsing into dataclasses lives in
ApiProvider. All ML results are pre-computed; this client never triggers
scoring (plans/plan.md section 10.3).
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_S = 1.5


class ApiClient:
    """httpx wrapper around the plan section 10.1 endpoints."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_s,
            transport=transport,
        )

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()

    def get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        """GET JSON from path. Raises httpx.HTTPError on transport failure."""
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def health(self) -> dict:
        """GET /health."""
        return self.get("/health")

    def get_alerts(self, params: Optional[dict[str, Any]] = None) -> Any:
        """GET /alerts."""
        return self.get("/alerts", params=params)

    def get_alert_detail(self, tx_id: int) -> dict:
        """GET /alerts/{tx_id}."""
        return self.get(f"/alerts/{tx_id}")

    def get_graph(self, tx_id: int, depth: int = 1) -> dict:
        """GET /graph/{tx_id}?depth=."""
        return self.get(f"/graph/{tx_id}", params={"depth": depth})

    def get_community(self, community_id: int) -> dict:
        """GET /communities/{community_id}."""
        return self.get(f"/communities/{community_id}")

    def get_stats_summary(self) -> dict:
        """GET /stats/summary."""
        return self.get("/stats/summary")

    def get_pipeline_status(self) -> dict:
        """GET /pipeline/status."""
        return self.get("/pipeline/status")


# Module-level helpers kept for earlier call sites / tests.
def get_alerts(params: dict | None = None) -> list[dict]:
    """GET /alerts via a one-shot client (prefer ApiClient in new code)."""
    client = ApiClient()
    try:
        return client.get_alerts(params)
    finally:
        client.close()


def get_alert_detail(tx_id: int) -> dict:
    """GET /alerts/{tx_id} via a one-shot client."""
    client = ApiClient()
    try:
        return client.get_alert_detail(tx_id)
    finally:
        client.close()


def get_graph(tx_id: int, depth: int = 1) -> dict:
    """GET /graph/{tx_id} via a one-shot client."""
    client = ApiClient()
    try:
        return client.get_graph(tx_id, depth)
    finally:
        client.close()


def get_community(community_id: int) -> dict:
    """GET /communities/{community_id} via a one-shot client."""
    client = ApiClient()
    try:
        return client.get_community(community_id)
    finally:
        client.close()


def get_stats_summary() -> dict:
    """GET /stats/summary via a one-shot client."""
    client = ApiClient()
    try:
        return client.get_stats_summary()
    finally:
        client.close()


def get_pipeline_status() -> dict:
    """GET /pipeline/status via a one-shot client."""
    client = ApiClient()
    try:
        return client.get_pipeline_status()
    finally:
        client.close()
