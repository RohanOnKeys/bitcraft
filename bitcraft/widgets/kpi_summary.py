"""KPI summary panel: top-line dashboard stats from the store."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from bitcraft.helpers import stub_chart
from bitcraft.helpers.format import format_int, format_pct
from bitcraft.widgets.chart import sparkline

# Stub 16-point trends under each KPI until the API serves history.
_TREND = stub_chart.alerts_by_timestep
SPARK_SERIES = {
    "#kpi-tx": _TREND(21)[:16],
    "#kpi-alerts": _TREND(22)[18:34],
    "#kpi-critical": _TREND(3)[18:34],
    "#kpi-labeled": _TREND(24)[:16],
    "#kpi-network": _TREND(25)[30:46],
    "#kpi-pipeline": _TREND(26)[8:24],
}


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
            text = Text.from_markup(f"{value}\n[#8a8078]{label}[/]\n")
            text.append_text(sparkline(SPARK_SERIES[cid]))
            text.justify = "center"
            cell.update(text)
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
            f"[italic #ffb6c1]~{format_pct(stats.network_coverage_pct)}[/]",
            "network",
        )
        pipe = pipeline.status if pipeline else "--"
        set_cell("#kpi-pipeline", f"[bold #fa8072]{pipe}[/]", "pipeline")
