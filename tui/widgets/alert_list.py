"""Ranked, filterable alert list backed by the store."""

from __future__ import annotations

from textual.widgets import DataTable

from tui.helpers.format import network_cell, score_bar
from tui.helpers.severity import severity_for_score
from tui.providers.models import AlertSummary


class AlertList(DataTable):
    """Paginated table of ranked alerts."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns(
            "rank",
            "tx",
            "sev",
            "score",
            "anom",
            "community",
            "network",
            "step",
            "triage",
        )
        self.refresh_from_store()

    def refresh_from_store(self) -> None:
        """Reload rows from store.alert_page."""
        self.clear()
        store = self.app.store
        page = store.alert_page
        if page is None:
            return
        for row in page.items:
            self._add_alert_row(row)

    def _add_alert_row(self, row: AlertSummary) -> None:
        store = self.app.store
        tier = row.severity or severity_for_score(row.composite_score)
        community = "--"
        if row.community_id is not None:
            community = f"{row.community_id}/{row.community_risk:.0%}"
        step = str(row.timestep) if row.timestep is not None else "--"
        triage = store.triage.get(row.elliptic_tx_id)
        mark = triage.status[0].upper() if triage and triage.status != "unmarked" else ""
        self.add_row(
            str(row.rank),
            str(row.elliptic_tx_id),
            tier[:4].upper(),
            f"{row.composite_score:.2f} {score_bar(row.composite_score, 8)}",
            f"{row.anomaly_score:.2f}",
            community,
            network_cell(row.has_network_layer, row.network_signal),
            step,
            mark,
            key=str(row.elliptic_tx_id),
        )
