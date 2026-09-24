"""Dashboard screen: KPIs, filters, ranked alerts, preview."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from tui.helpers.format import network_cell, score_bar
from tui.helpers.severity import severity_for_score
from tui.providers.demo_provider import (
    ANOMALY_WEIGHT,
    COMMUNITY_WEIGHT,
    NETWORK_WEIGHT,
)
from tui.providers.models import ProviderError
from tui.screens.alert_detail import AlertDetailScreen
from tui.widgets.alert_list import AlertList
from tui.widgets.filter_panel import FilterPanel
from tui.widgets.header_bar import HeaderBar
from tui.widgets.kpi_summary import KpiSummary
from tui.widgets.panel_state import PanelState


class DashboardScreen(Screen):
    """Investigation dashboard backed by the app store."""

    BINDINGS = [
        ("f", "focus_filters", "Filters"),
        ("x", "reset_filters", "Reset"),
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("s", "cycle_sort", "Sort"),
        ("r", "refresh", "Refresh"),
        ("enter", "open_detail", "Detail"),
    ]

    def compose(self) -> ComposeResult:
        yield HeaderBar(id="header-bar")
        with Vertical(id="dashboard"):
            yield Static(
                "terminal too small (need 100x30)",
                id="size-guard",
            )
            yield KpiSummary(id="kpi-summary")
            with Horizontal(id="dashboard-body"):
                with Vertical(id="left-col"):
                    yield FilterPanel(id="filter-panel")
                    yield Static("", id="score-histogram")
                with Vertical(id="center-col"):
                    yield AlertList(id="alert-list")
                    yield Static("", id="alert-status")
                    yield PanelState(
                        state="empty",
                        message="",
                        id="alert-empty",
                    )
                yield Static("", id="preview-pane")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#alert-empty").display = False
        self._apply_size_guard()
        self._refresh_all()
        self.set_interval(0.5, self._apply_size_guard)
        try:
            self.query_one("#alert-list", AlertList).focus()
        except Exception:
            pass

    def on_screen_resume(self) -> None:
        """Refresh when boot pops and this mode screen becomes visible."""
        self._refresh_all()
        try:
            self.query_one("#alert-list", AlertList).focus()
        except Exception:
            pass

    def on_resize(self, event) -> None:  # type: ignore[no-untyped-def]
        self._apply_size_guard()

    def _apply_size_guard(self) -> None:
        small = self.size.width < 100 or self.size.height < 30
        self.query_one("#size-guard").display = small
        self.query_one("#kpi-summary").display = not small
        self.query_one("#dashboard-body").display = not small
        wide = self.size.width >= 120
        self.query_one("#preview-pane").display = wide and not small

    def _refresh_all(self) -> None:
        self.query_one("#kpi-summary", KpiSummary).refresh_from_store()
        self.query_one("#alert-list", AlertList).refresh_from_store()
        self._update_status()
        self._update_histogram()
        self._update_preview()

    def _update_status(self) -> None:
        page = self.app.store.alert_page
        status = self.query_one("#alert-status", Static)
        empty = self.query_one("#alert-empty", PanelState)
        if page is None:
            status.update("no data")
            return
        if page.total == 0:
            self.query_one("#alert-list").display = False
            empty.display = True
            empty.set_empty(
                "No alerts match these filters.",
                "Press x to reset.",
            )
            status.update("showing 0 of 0")
            return
        self.query_one("#alert-list").display = True
        empty.display = False
        start = page.offset + 1
        end = page.offset + len(page.items)
        status.update(f"showing {start}-{end} of {page.total:,}")

    def _update_histogram(self) -> None:
        page = self.app.store.alert_page
        hist = self.query_one("#score-histogram", Static)
        if page is None or not page.items:
            hist.update("score hist\n(no data)")
            return
        buckets = [0] * 10
        for row in page.items:
            idx = min(9, int(row.composite_score * 10))
            buckets[idx] += 1
        peak = max(buckets) or 1
        lines = ["score hist"]
        for i, count in enumerate(buckets):
            bar_w = int(round(count / peak * 12))
            lines.append(f"{i/10:.1f} {'#' * bar_w}")
        hist.update("\n".join(lines))

    def _update_preview(self) -> None:
        preview = self.query_one("#preview-pane", Static)
        store = self.app.store
        row = store.selected_alert()
        if row is None and store.alert_page and store.alert_page.items:
            row = store.alert_page.items[0]
            store.select_tx(row.elliptic_tx_id)
        if row is None:
            preview.update("preview\n(no selection)")
            return
        tier = row.severity or severity_for_score(row.composite_score)
        wa = ANOMALY_WEIGHT * row.anomaly_score
        wc = COMMUNITY_WEIGHT * row.community_risk
        wn = NETWORK_WEIGHT * row.network_signal
        net = network_cell(row.has_network_layer, row.network_signal)
        preview.update(
            "preview\n"
            f"tx {row.elliptic_tx_id}\n"
            f"sev {tier}\n"
            f"score {row.composite_score:.3f} {score_bar(row.composite_score)}\n"
            f"anomaly x0.60  {wa:.3f} {score_bar(wa)}\n"
            f"community x0.25  {wc:.3f} {score_bar(wc)}\n"
            f"network x0.15  {wn:.3f} {score_bar(wn)}\n"
            f"synthetic {'yes' if row.has_synthetic_layer else 'no'}\n"
            f"network {net}\n"
        )

    def _reload_alerts(self) -> None:
        store = self.app.store

        def work() -> None:
            try:
                page = store.provider.alerts(store.filters.to_query())
                store.set_alert_page(page)
                store.last_error = None
            except ProviderError as exc:
                store.last_error = str(exc)

        # Run inline for simplicity; workers used for longer fetches.
        work()
        self._refresh_all()

    def on_data_table_row_highlighted(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.data_table.id != "alert-list":
            return
        if event.row_key is None:
            return
        try:
            tx_id = int(str(event.row_key.value))
        except ValueError:
            return
        self.app.store.select_tx(tx_id)
        self._update_preview()

    def on_data_table_row_selected(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.data_table.id != "alert-list":
            return
        self.action_open_detail()

    def on_input_changed(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.input.id not in {
            "filter-min-score",
            "filter-community",
            "filter-severity",
        }:
            return
        self.set_timer(0.25, self._apply_filters)

    def on_checkbox_changed(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.checkbox.id in {"filter-network", "filter-synthetic"}:
            self._apply_filters()

    def _apply_filters(self) -> None:
        self.query_one("#filter-panel", FilterPanel).read_into_store()
        self._reload_alerts()

    def action_focus_filters(self) -> None:
        self.query_one("#filter-min-score").focus()

    def action_reset_filters(self) -> None:
        self.query_one("#filter-panel", FilterPanel).reset_filters()
        self._reload_alerts()

    def action_next_page(self) -> None:
        store = self.app.store
        page = store.alert_page
        if page is None:
            return
        nxt = page.offset + page.limit
        if nxt >= page.total:
            return
        store.filters.offset = nxt
        self._reload_alerts()

    def action_prev_page(self) -> None:
        store = self.app.store
        page = store.alert_page
        if page is None:
            return
        prev = max(0, page.offset - page.limit)
        store.filters.offset = prev
        self._reload_alerts()

    def action_cycle_sort(self) -> None:
        order = ["rank", "anomaly", "community", "network"]
        store = self.app.store
        try:
            idx = order.index(store.filters.sort)
        except ValueError:
            idx = 0
        store.filters.sort = order[(idx + 1) % len(order)]
        store.filters.offset = 0
        self._reload_alerts()

    def action_refresh(self) -> None:
        self._reload_alerts()
        self.query_one("#kpi-summary", KpiSummary).refresh_from_store()

    def action_open_detail(self) -> None:
        tx_id = self.app.store.selected_tx_id
        if tx_id is None and self.app.store.alert_page and self.app.store.alert_page.items:
            tx_id = self.app.store.alert_page.items[0].elliptic_tx_id
        if tx_id is None:
            return
        self.app.push_screen(AlertDetailScreen(elliptic_tx_id=tx_id))
