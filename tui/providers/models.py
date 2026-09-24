"""Shared data models for TUI providers.

Field names match backend/app/schemas exactly. Optional fields the backend
does not yet expose are marked as extensions (see plans/future.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


Provenance = Literal["real", "modeled"]
SeverityTier = Literal["critical", "high", "medium", "low"]


@dataclass(frozen=True)
class Health:
    """Backend liveness payload (mirrors GET /health)."""

    status: str


@dataclass(frozen=True)
class StatsSummary:
    """Dashboard KPI summary (mirrors GET /stats/summary)."""

    total_transactions: int
    total_alerts: int
    labeled_coverage_pct: float
    network_coverage_pct: float
    full_stack_coverage_pct: float


@dataclass(frozen=True)
class PipelineStatus:
    """Last/running ML pipeline job status (mirrors GET /pipeline/status)."""

    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class AlertQuery:
    """Filter, sort, and paging parameters for alert list requests."""

    offset: int = 0
    limit: int = 100
    min_score: Optional[float] = None
    community_id: Optional[int] = None
    severities: tuple[SeverityTier, ...] = ()
    network_required: bool = False
    synthetic_required: bool = False
    sort: str = "rank"  # rank | anomaly | community | network


@dataclass(frozen=True)
class AlertSummary:
    """One row in the paginated ranked alert list."""

    elliptic_tx_id: int
    composite_score: float
    anomaly_score: float
    community_risk: float
    network_signal: float
    rank: int
    has_synthetic_layer: bool
    has_network_layer: bool
    # extension, see future.md
    timestep: Optional[int] = None
    community_id: Optional[int] = None
    severity: Optional[SeverityTier] = None


@dataclass(frozen=True)
class EvidenceItem:
    """One structured evidence row with provenance.

    extension, see future.md: backend currently returns only evidence_text.
    """

    label: str
    value: str
    provenance: Provenance


@dataclass(frozen=True)
class ShapReason:
    """One SHAP feature contribution (feature-index level only)."""

    feature_index: int
    contribution: float


@dataclass(frozen=True)
class AlertDetail:
    """Full alert detail including SHAP and evidence."""

    elliptic_tx_id: int
    composite_score: float
    anomaly_score: float
    community_risk: float
    network_signal: float
    rank: int
    has_synthetic_layer: bool
    has_network_layer: bool
    evidence_text: str
    shap_reasons: Optional[list[ShapReason]] = None
    # extension, see future.md
    timestep: Optional[int] = None
    community_id: Optional[int] = None
    severity: Optional[SeverityTier] = None
    evidence_items: Optional[list[EvidenceItem]] = None


@dataclass(frozen=True)
class AlertPage:
    """One page of ranked alerts plus total matching count."""

    items: list[AlertSummary]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class GraphNode:
    """One transaction node in a subgraph response."""

    elliptic_tx_id: int
    composite_score: Optional[float] = None
    community_id: Optional[int] = None


@dataclass(frozen=True)
class GraphEdge:
    """One relationship edge in a subgraph response."""

    source_tx_id: int
    target_tx_id: int
    relationship_type: str
    data_source: str


@dataclass(frozen=True)
class Subgraph:
    """Subgraph around one transaction, out to the requested depth."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


@dataclass(frozen=True)
class CommunitySummary:
    """Compact community row for overview lists."""

    community_id: int
    size: int
    illicit_ratio: Optional[float]
    mean_pagerank: float
    alert_count: int = 0


@dataclass(frozen=True)
class CommunityDetail:
    """Community members, size, and illicit ratio."""

    community_id: int
    size: int
    illicit_ratio: Optional[float]
    mean_pagerank: float
    member_tx_ids: list[int]


@dataclass(frozen=True)
class ThreatOverview:
    """Aggregates for the threat detection screen.

    extension, see future.md: no dedicated backend endpoint yet; DemoProvider
    synthesizes this, ApiProvider may approximate from available endpoints.
    """

    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    no_network_evidence_count: int
    high_illicit_community_count: int
    alerts_per_timestep: Optional[dict[int, int]] = None


@dataclass
class ProviderError(Exception):
    """Typed provider failure for UI error panels (never raw exceptions)."""

    message: str
    cause: Optional[BaseException] = None

    def __str__(self) -> str:
        return self.message
