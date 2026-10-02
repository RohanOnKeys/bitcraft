"""Graph explorer: connectivity graph plus supporting chart panels.

Stub data throughout (tui/helpers/stub_charts.py) until the graph endpoints
land; the layout and widgets are the real ones.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from tui.helpers import stub_charts
from tui.widgets.chart_panels import (
    CommunityBars,
    DegreeChart,
    DonutChart,
    FlowChart,
    HeatmapChart,
    StatTiles,
    TimestepChart,
)
from tui.helpers.drivers import weighted_parts
from tui.widgets.chart_panels import DRIVER_COLOURS
from tui.widgets.charts import CHROME, CRIMSON, MUTED, ORANGE, PINK, SALMON, YELLOW
from tui.widgets.graph_view import GraphView, graph_legend
from tui.widgets.header_bar import HeaderBar
from tui.widgets.mascot import NATIVE_WIDTH, Mascot

# Below these sizes the frog gives its room back to the charts.
MASCOT_MIN_WIDTH = 150
MASCOT_MIN_HEIGHT = 46


class GraphExplorerScreen(Screen):
    """Full-page link analysis: live connectivity graph and chart panels."""

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        with Vertical(id="graph-page"):
            with Horizontal(id="graph-top"):
                with Vertical(id="graph-main", classes="panel"):
                    yield GraphView(id="graph-view")
                    yield Static(graph_legend(), id="graph-legend")
                with Vertical(id="graph-side"):
                    yield StatTiles(
                        [
                            ("nodes", "2,184", stub_charts.alerts_by_timestep(1), YELLOW),
                            ("edges", "6,911", stub_charts.alerts_by_timestep(2), CHROME),
                            ("communities", "41", stub_charts.alerts_by_timestep(4), ORANGE),
                            ("density", "0.0029", stub_charts.alerts_by_timestep(6), SALMON),
                            ("max degree", "412", stub_charts.degree_distribution(), PINK),
                        ],
                        id="graph-stats",
                        classes="panel",
                    )
                    yield Mascot("happy", art_width=NATIVE_WIDTH, idle=True, id="graph-mascot")
            with Horizontal(id="graph-bottom"):
                yield TimestepChart(id="graph-timeline", classes="panel")
                yield DonutChart(
                    [(n, v, c) for (n, v), c in zip(
                        stub_charts.score_mix(), (CRIMSON, ORANGE, YELLOW, MUTED)
                    )],
                    label="4,483",
                    sublabel="alerts",
                    id="graph-severity",
                    classes="panel",
                )
                yield DonutChart(
                    [(n, v, c) for (n, v), c in zip(
                        stub_charts.driver_mix(), (SALMON, CHROME, PINK)
                    )],
                    label="0.87",
                    sublabel="score",
                    id="graph-drivers",
                    classes="panel",
                )
                yield CommunityBars(id="graph-communities", classes="panel")
            with Horizontal(id="graph-bottom-2"):
                yield FlowChart(id="graph-flow", classes="panel")
                yield HeatmapChart(id="graph-heatmap", classes="panel")
                yield DegreeChart(id="graph-degree", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        titles = {
            "#graph-main": "connectivity · focus neighbourhood (depth 2)",
            "#graph-stats": "graph stats",
            "#graph-drivers": "score drivers",
            "#graph-timeline": "alerts per timestep",
            "#graph-severity": "severity mix",
            "#graph-communities": "riskiest communities",
            "#graph-flow": "BTC flow · focus neighbourhood",
            "#graph-heatmap": "activity · weekday x hour (UTC)",
            "#graph-degree": "degree distribution",
        }
        for selector, title in titles.items():
            self.query_one(selector).border_title = title
        self._sync_focus()
        self._sync_live()
        self._fit()

    def on_screen_resume(self) -> None:
        self._sync_focus()
        self._sync_live()

    def _sync_live(self) -> None:
        """Swap sample panels for store data wherever the provider has it."""
        store = self.app.store
        threat, stats, page = store.threat_overview, store.stats, store.alert_page
        per_ts: list[float] = []
        if threat is not None and threat.alerts_per_timestep:
            series = threat.alerts_per_timestep
            per_ts = [float(series.get(t, 0)) for t in range(1, max(series) + 1)]
            self.query_one("#graph-timeline", TimestepChart).series = per_ts
        if threat is not None:
            tiers = (
                ("critical", threat.critical_count, CRIMSON),
                ("high", threat.high_count, ORANGE),
                ("medium", threat.medium_count, YELLOW),
                ("low", threat.low_count, MUTED),
            )
            donut = self.query_one("#graph-severity", DonutChart)
            donut.segments = [t for t in tiers if t[1] > 0] or list(tiers)
            donut.label = f"{sum(t[1] for t in tiers):,}"
        if page is not None and page.items:
            sums = {"MODEL": 0.0, "ANOMALY": 0.0, "COMMUNITY": 0.0, "NETWORK": 0.0}
            for row in page.items:
                parts = weighted_parts(
                    row.anomaly_score, row.community_risk, row.network_signal, row.model_score
                )
                for key, value in parts.items():
                    sums[key] += value
            drivers = self.query_one("#graph-drivers", DonutChart)
            drivers.segments = [
                (k.lower(), v, DRIVER_COLOURS[k]) for k, v in sums.items() if v > 0
            ]
            mean = sum(r.composite_score for r in page.items) / len(page.items)
            drivers.label = f"{mean:.2f}"
            drivers.sublabel = "mean"
        ranked = [c for c in store.communities if c.illicit_ratio is not None]
        if ranked:
            self.query_one("#graph-communities", CommunityBars).rows = [
                (f"C{c.community_id}", float(c.illicit_ratio), c.size) for c in ranked[:8]
            ]
        if stats is not None:
            trend = per_ts or stub_charts.alerts_by_timestep(1)
            crit = threat.critical_count if threat is not None else 0
            self.query_one("#graph-stats", StatTiles).stats = [
                ("transactions", f"{stats.total_transactions:,}", trend, YELLOW),
                ("alerts", f"{stats.total_alerts:,}", trend, CHROME),
                ("critical", f"{crit:,}", trend, ORANGE),
                ("labeled", f"{stats.labeled_coverage_pct:.1f}%", trend, SALMON),
                ("network cov.", f"{stats.network_coverage_pct:.1f}%", trend, PINK),
            ]
        for selector in ("#graph-timeline", "#graph-severity", "#graph-drivers",
                         "#graph-communities", "#graph-stats"):
            self.query_one(selector).refresh()

    def on_resize(self, event) -> None:  # type: ignore[no-untyped-def]
        self._fit()

    def _sync_focus(self) -> None:
        tx = self.app.store.selected_tx_id
        self.query_one("#graph-view", GraphView).set_focus_tx(tx)
        self.query_one("#graph-main").border_subtitle = f"tx {tx or 10000021}"

    def _fit(self) -> None:
        w, h = self.size.width, self.size.height
        self.query_one("#graph-mascot").display = w >= MASCOT_MIN_WIDTH and h >= MASCOT_MIN_HEIGHT
        self.query_one("#graph-side").styles.width = NATIVE_WIDTH + 2 if w >= MASCOT_MIN_WIDTH else 40
        self.query_one("#graph-bottom-2").display = h >= 40
        self.query_one("#graph-drivers").display = w >= 160
