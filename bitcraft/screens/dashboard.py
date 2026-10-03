"""Dashboard screen: KPIs, filters, ranked alerts, preview."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from bitcraft.helpers.format import network_cell
from bitcraft.helpers.severity import severity_for_score
from bitcraft.providers.demo_provider import (
    ANOMALY_WEIGHT,
    COMMUNITY_WEIGHT,
    MODEL_WEIGHT,
    NETWORK_WEIGHT,
)
from bitcraft.providers.models import ProviderError
from bitcraft.screens.alert_detail import AlertDetailScreen
from bitcraft.widgets.alert_list import AlertList
from bitcraft.widgets.chart_panel import DRIVER_COLOURS, driver_bars, score_gauge, severity_colour
from bitcraft.widgets.chart import MUTED, TEXT, YELLOW, column_chart
from bitcraft.widgets.filter_panel import FilterPanel
from bitcraft.widgets.header_bar import HeaderBar
from bitcraft.widgets.kpi_summary import KpiSummary
from bitcraft.widgets.graph_view import GraphView
from bitcraft.widgets.panel_state import PanelState


# Terminal width at which the preview column widens for bigger charts.
WIDE_PREVIEW_MIN_WIDTH = 160


class DashboardScreen(Screen):
    """Investigation dashboard backed by the app store."""

    BINDINGS = [
        ("f", "focus_filters", "Filters"),
        ("x", "reset_filters", "Reset"),
        ("n", "next_page", "Next"),
        ("p", "prev_page", "Prev"),
        ("s", "cycle_sort", "Sort"),
        ("r", "refresh", "Refresh"),
        ("m", "mark", "Mark"),
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
                    yield Static("", id="score-histogram", classes="panel")
                with Vertical(id="center-col"):
                    yield AlertList(id="alert-list")
                    yield Static("", id="alert-status")
                    yield PanelState(
                        state="empty",
                        message="",
                        id="alert-empty",
                    )
                with Vertical(id="preview-col"):
                    yield Static("", id="preview-pane", classes="panel")
                    yield GraphView(clusters=3, labels=False, id="preview-graph", classes="panel")
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
        self.query_one("#preview-col").display = wide and not small
        self.query_one("#preview-col").styles.width = (
            58 if self.size.width >= WIDE_PREVIEW_MIN_WIDTH else 36
        )

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
        hist.border_title = "scores · this page"
        if page is None or not page.items:
            hist.update("(no data)")
            return
        buckets = [0] * 12
        for row in page.items:
            buckets[min(11, int(row.composite_score * 12))] += 1
        height = max(3, hist.content_size.height - 2 or 8)
        chart = column_chart([float(b) for b in buckets], height, gap=True)
        chart.append("\n")
        chart.append("0.0" + " " * 17 + "1.0", Style(color=MUTED))
        chart.append("\n")
        chart.append(f"peak {max(buckets)} alerts", Style(color=YELLOW, bold=True))
        hist.update(chart)

    def _update_preview(self) -> None:
        preview = self.query_one("#preview-pane", Static)
        preview.border_title = "preview"
        store = self.app.store
        row = store.selected_alert()
        if row is None and store.alert_page and store.alert_page.items:
            row = store.alert_page.items[0]
            store.select_tx(row.elliptic_tx_id)
        graph = self.query_one("#preview-graph", GraphView)
        if row is None:
            preview.update("(no selection)")
            return
        tier = row.severity or severity_for_score(row.composite_score)
        graph.set_focus_tx(row.elliptic_tx_id)
        graph.border_title = f"neighbourhood · tx {row.elliptic_tx_id}"
        wm = MODEL_WEIGHT * (row.model_score or 0.0)
        wa = ANOMALY_WEIGHT * row.anomaly_score
        wc = COMMUNITY_WEIGHT * row.community_risk
        wn = NETWORK_WEIGHT * row.network_signal
        net = network_cell(row.has_network_layer, row.network_signal)
        bar_w = max(8, preview.content_size.width - 22)
        text = Text(no_wrap=True, end="")
        text.append("tx ", Style(color=MUTED))
        text.append(f"{row.elliptic_tx_id}", Style(color=YELLOW, bold=True))
        text.append("  ")
        text.append(f" {tier.upper()} ", Style(color="#000000", bgcolor=severity_colour(tier), bold=True))
        text.append(f"  rank {row.rank}\n\n", Style(color=MUTED))
        text.append("score     ", Style(color=MUTED))
        text.append_text(score_gauge(row.composite_score, bar_w + 1))
        text.append("\n\n")
        text.append_text(driver_bars(
            [
                ("risk model", wm, DRIVER_COLOURS["MODEL"]),
                ("anomaly", wa, DRIVER_COLOURS["ANOMALY"]),
                ("community", wc, DRIVER_COLOURS["COMMUNITY"]),
                ("network", wn, DRIVER_COLOURS["NETWORK"]),
            ],
            bar_w,
        ))
        text.append("\n\n")
        text.append("weights   ", Style(color=MUTED))
        text.append(
            f"x{MODEL_WEIGHT:.2f} · x{ANOMALY_WEIGHT:.2f} · x{COMMUNITY_WEIGHT:.2f} · x{NETWORK_WEIGHT:.2f}\n",
            Style(color=TEXT),
        )
        text.append("synthetic ", Style(color=MUTED))
        text.append(("yes" if row.has_synthetic_layer else "no") + "\n", Style(color=YELLOW))
        text.append("network   ", Style(color=MUTED))
        text.append(net, Style(color=YELLOW if row.has_network_layer else MUTED, italic=True))
        preview.update(text)

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
        # Debounced from on_input_changed; the screen may be gone by now.
        if not self.is_attached:
            return
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

    def action_mark(self) -> None:
        """Cycle the highlighted alert's triage mark: reviewed, escalate,
        dismiss, unmarked. Marks last for the session."""
        tx_id = self.app.store.selected_tx_id
        if tx_id is None:
            return
        status = self.app.store.cycle_triage(tx_id)
        self.query_one(AlertList).show_triage(tx_id)
        self.notify(f"tx {tx_id}: {status}", timeout=2)

    def action_open_detail(self) -> None:
        tx_id = self.app.store.selected_tx_id
        if tx_id is None and self.app.store.alert_page and self.app.store.alert_page.items:
            tx_id = self.app.store.alert_page.items[0].elliptic_tx_id
        if tx_id is None:
            return
        self.app.push_screen(AlertDetailScreen(elliptic_tx_id=tx_id))
