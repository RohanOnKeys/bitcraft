"""Filter panel: alert list filtering controls wired to the store."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Checkbox, Input, Label, Static


class FilterPanel(Widget):
    """Filter controls for the ranked alert list."""

    def compose(self) -> ComposeResult:
        with Vertical(id="filter-body"):
            yield Label("Filters", classes="accent")
            yield Static("min score", classes="filter-label")
            yield Input(placeholder="0.0", id="filter-min-score")
            yield Static("community id", classes="filter-label")
            yield Input(placeholder="any", id="filter-community")
            yield Static("severity (csv)", classes="filter-label")
            yield Input(placeholder="critical,high", id="filter-severity")
            yield Checkbox("network required", id="filter-network")
            yield Checkbox("synthetic required", id="filter-synthetic")
            yield Static(
                "f focus  x reset",
                classes="modeled-badge",
                id="filter-status",
            )

    def read_into_store(self) -> None:
        """Parse inputs into store.filters."""
        store = self.app.store
        min_raw = self.query_one("#filter-min-score", Input).value.strip()
        store.filters.min_score = float(min_raw) if min_raw else None
        comm_raw = self.query_one("#filter-community", Input).value.strip()
        store.filters.community_id = int(comm_raw) if comm_raw.isdigit() else None
        sev_raw = self.query_one("#filter-severity", Input).value.strip()
        if sev_raw:
            store.filters.severities = tuple(
                s.strip().lower() for s in sev_raw.split(",") if s.strip()
            )
        else:
            store.filters.severities = ()
        store.filters.network_required = self.query_one(
            "#filter-network", Checkbox
        ).value
        store.filters.synthetic_required = self.query_one(
            "#filter-synthetic", Checkbox
        ).value
        store.filters.offset = 0

    def reset_filters(self) -> None:
        """Clear all filter inputs and store filter state."""
        self.query_one("#filter-min-score", Input).value = ""
        self.query_one("#filter-community", Input).value = ""
        self.query_one("#filter-severity", Input).value = ""
        self.query_one("#filter-network", Checkbox).value = False
        self.query_one("#filter-synthetic", Checkbox).value = False
        store = self.app.store
        store.filters.min_score = None
        store.filters.community_id = None
        store.filters.severities = ()
        store.filters.network_required = False
        store.filters.synthetic_required = False
        store.filters.offset = 0
        store.filters.sort = "rank"
