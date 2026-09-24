"""DataProvider protocol: swappable demo vs FastAPI backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tui.providers.models import (
    AlertDetail,
    AlertPage,
    AlertQuery,
    CommunityDetail,
    CommunitySummary,
    Health,
    PipelineStatus,
    StatsSummary,
    Subgraph,
    ThreatOverview,
)


@runtime_checkable
class DataProvider(Protocol):
    """Read-only data contract mirroring the FastAPI surface.

    Screens never construct providers; they go through the app store.
    """

    @property
    def source_label(self) -> str:
        """Short label for the header badge (DEMO DATA or API)."""
        ...

    def health(self) -> Health:
        """Liveness check."""
        ...

    def stats_summary(self) -> StatsSummary:
        """Dashboard KPIs."""
        ...

    def alerts(self, query: AlertQuery) -> AlertPage:
        """Paginated, filterable ranked alert list."""
        ...

    def alert_detail(self, tx_id: int) -> AlertDetail:
        """Full detail for one transaction alert."""
        ...

    def subgraph(self, tx_id: int, depth: int = 1) -> Subgraph:
        """Ego subgraph around one transaction."""
        ...

    def community(self, community_id: int) -> CommunityDetail:
        """One community with member ids."""
        ...

    def top_communities(self, limit: int = 25) -> list[CommunitySummary]:
        """Highest-risk or largest communities for overview."""
        ...

    def threat_overview(self) -> ThreatOverview:
        """Aggregates for the threat detection screen."""
        ...

    def pipeline_status(self) -> PipelineStatus:
        """Last/running offline pipeline job status."""
        ...
