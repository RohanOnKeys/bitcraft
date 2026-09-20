"""Ranked, filterable alert list."""

from textual.widgets import DataTable


class AlertList(DataTable):
    """Paginated table of ranked alerts, backed by GET /alerts."""

    def on_mount(self) -> None:
        self.add_columns("rank", "elliptic_tx_id", "composite_score", "community_risk")
