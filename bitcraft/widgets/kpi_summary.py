"""KPI summary panel: top-line dashboard stats from the store."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from bitcraft.helpers.format import format_int, format_pct
from bitcraft.widgets.chart import sparkline

# Points per KPI sparkline; longer series are averaged into this many buckets.
SPARK_POINTS = 16


def bucket_means(values, n: int = SPARK_POINTS) -> list[float]:
    """Average a series into at most n equal buckets, keeping its shape."""
    values = [float(v) for v in values]
    if len(values) <= n:
        return values
    out = []
    for i in range(n):
        chunk = values[i * len(values) // n:(i + 1) * len(values) // n]
        out.append(sum(chunk) / len(chunk))
    return out


def spark_series(charts) -> dict[str, list[float]]:
    """Sparkline under each KPI: its count per timestep (1 to 49), and the
    pipeline's seconds per stage. Empty when the charts are not loaded."""
    if charts is None:
        return {}
    return {
        "#kpi-tx": bucket_means(charts.transactions),
        "#kpi-alerts": bucket_means(charts.alerts),
        "#kpi-critical": bucket_means(charts.critical),
        "#kpi-labeled": bucket_means(charts.labeled),
        "#kpi-network": bucket_means(charts.network),
        "#kpi-pipeline": bucket_means(charts.stage_seconds.values()),
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
        series = spark_series(store.charts)

        def set_cell(cid: str, value: str, label: str, extra_class: str | None = None) -> None:
            cell = self.query_one(cid, Static)
            text = Text.from_markup(f"{value}\n[#8a8078]{label}[/]\n")
            if series.get(cid):
                text.append_text(sparkline(series[cid]))
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
