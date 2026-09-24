"""ApiProvider: maps FastAPI JSON into TUI dataclasses.

Missing optional fields become None. HTTP and timeout errors become
ProviderError. Unknown data_source / relationship_type values are treated
as modeled (fail safe).
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from tui.api_client import ApiClient
from tui.helpers.severity import severity_for_score
from tui.providers.models import (
    AlertDetail,
    AlertPage,
    AlertQuery,
    AlertSummary,
    CommunityDetail,
    CommunitySummary,
    GraphEdge,
    GraphNode,
    Health,
    PipelineStatus,
    ProviderError,
    ShapReason,
    StatsSummary,
    Subgraph,
    ThreatOverview,
)

_REAL_SOURCES = {"elliptic", "real"}
_REAL_REL_TYPES = {"elliptic_edge", "elliptic"}


def _as_modeled_source(value: str) -> str:
    """Unknown provenance fails safe to modeled."""
    if value.lower() in _REAL_SOURCES:
        return value
    return value if value else "synthetic"


def _parse_shap(raw: Any) -> Optional[list[ShapReason]]:
    """Accept list-of-dicts or feature->score dict from the backend."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return [
            ShapReason(feature_index=int(k.replace("feature_", "") if isinstance(k, str) else k), contribution=float(v))
            for k, v in raw.items()
        ]
    if isinstance(raw, list):
        out: list[ShapReason] = []
        for item in raw:
            if isinstance(item, dict):
                out.append(
                    ShapReason(
                        feature_index=int(item.get("feature_index", item.get("index", 0))),
                        contribution=float(item.get("contribution", item.get("value", 0.0))),
                    )
                )
        return out
    return None


class ApiProvider:
    """Live FastAPI-backed provider. Never raises into the UI."""

    def __init__(self, client: ApiClient) -> None:
        self._client = client

    @property
    def source_label(self) -> str:
        """Header badge label."""
        return "API"

    def _call(self, fn, *args, **kwargs):
        """Run an api_client call and map errors to ProviderError."""
        try:
            return fn(*args, **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderError("backend timed out", cause=exc) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"backend HTTP {exc.response.status_code}", cause=exc
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"backend unreachable: {exc}", cause=exc) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError(f"unexpected backend payload: {exc}", cause=exc) from exc

    def health(self) -> Health:
        """GET /health."""
        data = self._call(self._client.health)
        return Health(status=str(data.get("status", "unknown")))

    def stats_summary(self) -> StatsSummary:
        """GET /stats/summary."""
        data = self._call(self._client.get_stats_summary)
        return StatsSummary(
            total_transactions=int(data["total_transactions"]),
            total_alerts=int(data["total_alerts"]),
            labeled_coverage_pct=float(data["labeled_coverage_pct"]),
            network_coverage_pct=float(data["network_coverage_pct"]),
            full_stack_coverage_pct=float(data["full_stack_coverage_pct"]),
        )

    def pipeline_status(self) -> PipelineStatus:
        """GET /pipeline/status."""
        data = self._call(self._client.get_pipeline_status)
        return PipelineStatus(
            status=str(data.get("status", "unknown")),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            error=data.get("error"),
        )

    def _parse_summary(self, item: dict) -> AlertSummary:
        """Parse one alert row; optional fields stay None when absent."""
        composite = float(item["composite_score"])
        has_network = bool(item["has_network_layer"])
        network_signal = float(item["network_signal"])
        if not has_network:
            network_signal = 0.0
        severity = item.get("severity")
        if severity is None:
            severity = severity_for_score(composite)
        return AlertSummary(
            elliptic_tx_id=int(item["elliptic_tx_id"]),
            composite_score=composite,
            anomaly_score=float(item["anomaly_score"]),
            community_risk=float(item["community_risk"]),
            network_signal=network_signal,
            rank=int(item["rank"]),
            has_synthetic_layer=bool(item["has_synthetic_layer"]),
            has_network_layer=has_network,
            timestep=item.get("timestep"),
            community_id=item.get("community_id"),
            severity=severity,
        )

    def alerts(self, query: AlertQuery) -> AlertPage:
        """GET /alerts with query params the backend may ignore today."""
        params: dict[str, Any] = {
            "offset": query.offset,
            "limit": query.limit,
            "sort": query.sort,
        }
        if query.min_score is not None:
            params["min_score"] = query.min_score
        if query.community_id is not None:
            params["community_id"] = query.community_id
        if query.severities:
            params["severity"] = ",".join(query.severities)
        if query.network_required:
            params["network_required"] = True
        if query.synthetic_required:
            params["synthetic_required"] = True

        data = self._call(self._client.get_alerts, params)
        if isinstance(data, list):
            items = [self._parse_summary(x) for x in data]
            return AlertPage(
                items=items, total=len(items), offset=query.offset, limit=query.limit
            )
        items = [self._parse_summary(x) for x in data.get("items", data.get("alerts", []))]
        return AlertPage(
            items=items,
            total=int(data.get("total", len(items))),
            offset=int(data.get("offset", query.offset)),
            limit=int(data.get("limit", query.limit)),
        )

    def alert_detail(self, tx_id: int) -> AlertDetail:
        """GET /alerts/{tx_id}."""
        data = self._call(self._client.get_alert_detail, tx_id)
        summary = self._parse_summary(data)
        return AlertDetail(
            elliptic_tx_id=summary.elliptic_tx_id,
            composite_score=summary.composite_score,
            anomaly_score=summary.anomaly_score,
            community_risk=summary.community_risk,
            network_signal=summary.network_signal,
            rank=summary.rank,
            has_synthetic_layer=summary.has_synthetic_layer,
            has_network_layer=summary.has_network_layer,
            evidence_text=str(data.get("evidence_text", "")),
            shap_reasons=_parse_shap(data.get("shap_reasons")),
            timestep=summary.timestep,
            community_id=summary.community_id,
            severity=summary.severity,
            evidence_items=None,  # extension; backend does not send yet
        )

    def subgraph(self, tx_id: int, depth: int = 1) -> Subgraph:
        """GET /graph/{tx_id}."""
        data = self._call(self._client.get_graph, tx_id, depth)
        nodes = [
            GraphNode(
                elliptic_tx_id=int(n["elliptic_tx_id"]),
                composite_score=n.get("composite_score"),
                community_id=n.get("community_id"),
            )
            for n in data.get("nodes", [])
        ]
        edges = []
        for e in data.get("edges", []):
            rel = str(e.get("relationship_type", "unknown"))
            src = str(e.get("data_source", "unknown"))
            # Fail safe: unknown provenance treated as modeled.
            if src.lower() not in _REAL_SOURCES and rel.lower() not in _REAL_REL_TYPES:
                src = _as_modeled_source(src)
            edges.append(
                GraphEdge(
                    source_tx_id=int(e["source_tx_id"]),
                    target_tx_id=int(e["target_tx_id"]),
                    relationship_type=rel,
                    data_source=src,
                )
            )
        return Subgraph(nodes=nodes, edges=edges)

    def community(self, community_id: int) -> CommunityDetail:
        """GET /communities/{community_id}."""
        data = self._call(self._client.get_community, community_id)
        return CommunityDetail(
            community_id=int(data["community_id"]),
            size=int(data["size"]),
            illicit_ratio=data.get("illicit_ratio"),
            mean_pagerank=float(data.get("mean_pagerank", 0.0)),
            member_tx_ids=[int(x) for x in data.get("member_tx_ids", [])],
        )

    def top_communities(self, limit: int = 25) -> list[CommunitySummary]:
        """No list endpoint yet; return empty and let UI show empty state."""
        # extension, see future.md: no GET /communities list endpoint
        return []

    def threat_overview(self) -> ThreatOverview:
        """Approximate from alerts page when no dedicated endpoint exists."""
        # extension, see future.md
        page = self.alerts(AlertQuery(offset=0, limit=500))
        crit = high = med = low = no_net = 0
        for row in page.items:
            tier = row.severity or severity_for_score(row.composite_score)
            if tier == "critical":
                crit += 1
            elif tier == "high":
                high += 1
            elif tier == "medium":
                med += 1
            else:
                low += 1
            if not row.has_network_layer:
                no_net += 1
        return ThreatOverview(
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low,
            no_network_evidence_count=no_net,
            high_illicit_community_count=0,
            alerts_per_timestep=None,
        )
