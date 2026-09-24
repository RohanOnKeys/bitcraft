"""Community table widget for the threat detection page."""

from __future__ import annotations

from textual.widgets import DataTable

from tui.providers.models import CommunitySummary


class CommunityTable(DataTable):
    """High-risk communities list."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("id", "size", "illicit", "pagerank", "alerts")
        self.refresh_from_store()

    def refresh_from_store(self) -> None:
        """Load communities from the store."""
        self.clear()
        for c in self.app.store.communities:
            self._add_row(c)

    def _add_row(self, c: CommunitySummary) -> None:
        illicit = "unlabeled" if c.illicit_ratio is None else f"{c.illicit_ratio:.2f}"
        self.add_row(
            str(c.community_id),
            str(c.size),
            illicit,
            f"{c.mean_pagerank:.4f}",
            str(c.alert_count),
            key=str(c.community_id),
        )
