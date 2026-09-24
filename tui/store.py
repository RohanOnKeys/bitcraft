"""App-level state and caches. Screens read from the store only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from tui.providers.models import (
    AlertPage,
    AlertQuery,
    AlertSummary,
    CommunitySummary,
    PipelineStatus,
    StatsSummary,
    ThreatOverview,
)
from tui.providers.provider import DataProvider


@dataclass
class FilterState:
    """Dashboard filter controls mirrored into AlertQuery."""

    min_score: Optional[float] = None
    community_id: Optional[int] = None
    severities: tuple[str, ...] = ()
    network_required: bool = False
    synthetic_required: bool = False
    sort: str = "rank"
    offset: int = 0
    limit: int = 100

    def to_query(self) -> AlertQuery:
        """Convert to an AlertQuery for the provider."""
        from tui.providers.models import SeverityTier

        sevs: list[SeverityTier] = []
        for s in self.severities:
            if s in ("critical", "high", "medium", "low"):
                sevs.append(s)  # type: ignore[arg-type]
        return AlertQuery(
            offset=self.offset,
            limit=self.limit,
            min_score=self.min_score,
            community_id=self.community_id,
            severities=tuple(sevs),
            network_required=self.network_required,
            synthetic_required=self.synthetic_required,
            sort=self.sort,
        )


@dataclass
class TriageMark:
    """Local-only triage state for one transaction."""

    status: str = "unmarked"  # unmarked | reviewed | escalate | dismiss
    note: str = ""


@dataclass
class Store:
    """Shared TUI state. Screens never construct providers themselves."""

    provider: DataProvider
    boot_log: list[str] = field(default_factory=list)
    stats: Optional[StatsSummary] = None
    pipeline: Optional[PipelineStatus] = None
    threat_overview: Optional[ThreatOverview] = None
    communities: list[CommunitySummary] = field(default_factory=list)
    alert_page: Optional[AlertPage] = None
    filters: FilterState = field(default_factory=FilterState)
    selected_tx_id: Optional[int] = None
    triage: dict[int, TriageMark] = field(default_factory=dict)
    last_error: Optional[str] = None
    is_demo: bool = True
    fast_boot: bool = False
    boot_complete: bool = False

    @property
    def source_label(self) -> str:
        """DEMO DATA or API badge text."""
        return self.provider.source_label

    def select_tx(self, tx_id: Optional[int]) -> None:
        """Remember the highlighted / opened transaction."""
        self.selected_tx_id = tx_id

    def set_alert_page(self, page: AlertPage) -> None:
        """Cache the current alert page."""
        self.alert_page = page

    def selected_alert(self) -> Optional[AlertSummary]:
        """Return the AlertSummary for selected_tx_id if present on the page."""
        if self.alert_page is None or self.selected_tx_id is None:
            return None
        for row in self.alert_page.items:
            if row.elliptic_tx_id == self.selected_tx_id:
                return row
        return None
