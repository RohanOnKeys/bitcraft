"""KPI summary panel: top-line dashboard stats from the store."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from tui.helpers.format import format_int, format_pct


class KpiSummary(Widget):
    """Six KPI cells from stats_summary and threat_overview."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="kpi-row"):
            yield Static("...", classes="kpi-cell", id="kpi-tx")
            yield Static("...", classes="kpi-cell", id="kpi-alerts")
            yield Static("...", classes="kpi-cell", id="kpi-critical")
            yield Static("...", classes="kpi-cell", id="kpi-labeled")
            yield Static("...", classes="kpi-cell", id="kpi-network")
            yield Static("...", classes="kpi-cell", id="kpi-pipeline")

    def on_mount(self) -> None:
        self.refresh_from_store()

    def refresh_from_store(self) -> None:
        """Rebuild cell text from the app store."""
        store = self.app.store
        stats = store.stats
        threat = store.threat_overview
        pipeline = store.pipeline

        def set_cell(cid: str, value: str, label: str, extra_class: str | None = None) -> None:
            cell = self.query_one(cid, Static)
            cell.update(f"{value}\n{label}")
            if extra_class:
                cell.add_class(extra_class)

        if stats is None:
            for cid in (
                "#kpi-tx",
                "#kpi-alerts",
                "#kpi-critical",
                "#kpi-labeled",
                "#kpi-network",
                "#kpi-pipeline",
            ):
                self.query_one(cid, Static).update("...\nloading")
            return

        set_cell("#kpi-tx", f"[bold #d4af37]{format_int(stats.total_transactions)}[/]", "transactions")
        set_cell("#kpi-alerts", f"[bold #d4af37]{format_int(stats.total_alerts)}[/]", "alerts")
        crit = threat.critical_count if threat else 0
        crit_style = "alert-high" if crit > 0 else None
        crit_txt = f"[bold #b3261e]{format_int(crit)}[/]" if crit > 0 else f"[bold #7a7a7a]{crit}[/]"
        set_cell("#kpi-critical", crit_txt, "critical", crit_style)
        set_cell(
            "#kpi-labeled",
            f"[bold #d4af37]{format_pct(stats.labeled_coverage_pct)}[/]",
            "labeled",
        )
        # Network coverage is synthetic-layer derived: modeled marker.
        set_cell(
            "#kpi-network",
            f"[italic #6a6a6a]~{format_pct(stats.network_coverage_pct)}[/]",
            "network",
        )
        pipe = pipeline.status if pipeline else "--"
        set_cell("#kpi-pipeline", f"[bold #7a7a7a]{pipe}[/]", "pipeline")
