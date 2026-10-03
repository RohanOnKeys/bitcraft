"""Threat detection screen: what to look at first, and why."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from bitcraft.helpers.drivers import primary_driver, weighted_parts
from bitcraft.helpers.severity import severity_for_score
from bitcraft.providers.models import AlertQuery, AlertSummary, ProviderError
from bitcraft.screens.alert_detail import AlertDetailScreen
from bitcraft.widgets.community_table import CommunityTable
from bitcraft.widgets.chart_panel import DRIVER_COLOURS, driver_bars, severity_colour
from bitcraft.widgets.chart import (
    CHROME,
    GOLD,
    MUTED,
    PINK,
    SALMON,
    TEXT,
    YELLOW,
    column_chart,
    gradient_bar,
    hbar,
)
from bitcraft.widgets.header_bar import HeaderBar
from bitcraft.widgets.stacked_bar import StackedBar

CAVEAT = "No network evidence is not the same as low risk"
# Terminal width at which the drivers column widens.
WIDE_SIDE_MIN_WIDTH = 150


class ThreatDetectionScreen(Screen):
    """Threat posture, queue, drivers, communities, signals, coverage."""

    BINDINGS = [
        ("enter", "open_detail", "Detail"),
        ("g", "open_graph", "Graph"),
        ("a", "filter_anomaly", "Anomaly"),
        ("c", "filter_community", "Community"),
        ("n", "filter_network_driver", "Network"),
        ("w", "toggle_network", "Net req"),
        ("r", "refresh", "Refresh"),
        ("1", "tab_all", "All"),
        ("2", "tab_critical", "Crit"),
        ("3", "tab_high", "High"),
        ("4", "tab_medium", "Med"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._queue: list[AlertSummary] = []
        self._cursor = 0
        self._severity_tab = "all"
        self._driver_filter: str | None = None
        self._network_only = False

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        with Vertical(id="threats"):
            yield Static("", id="threat-posture")
            yield StackedBar(id="threat-stack")
            with Horizontal(id="threat-body"):
                yield Static("", id="threat-queue", classes="panel")
                with Vertical(id="threat-side"):
                    yield Static("", id="threat-drivers", classes="panel")
                yield CommunityTable(id="threat-communities", classes="panel")
            with Horizontal(id="threat-bottom"):
                yield Static("", id="threat-signals", classes="panel")
                yield Static("", id="threat-coverage", classes="panel")
                yield Static("", id="threat-timeline", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self._fit()
        self.refresh_view()

    def on_resize(self, event) -> None:  # type: ignore[no-untyped-def]
        self._fit()

    def _fit(self) -> None:
        wide = self.size.width >= WIDE_SIDE_MIN_WIDTH
        self.query_one("#threat-side").styles.width = 48 if wide else 34

    def on_screen_resume(self) -> None:
        """Reload when switching back to the threats mode."""
        self.refresh_view()

    def refresh_view(self) -> None:
        """Reload queue and panels from provider/store."""
        store = self.app.store
        try:
            page = store.provider.alerts(
                AlertQuery(offset=0, limit=25, sort="rank")
            )
            self._queue = list(page.items)
        except ProviderError as exc:
            self.query_one("#threat-queue", Static).update(f"[!!] {exc}")
            return
        self._apply_local_filters()
        self._render_posture()
        self._render_queue()
        self._render_drivers()
        self.query_one("#threat-communities", CommunityTable).refresh_from_store()
        self._render_signals()
        self._render_coverage()
        self._render_timeline()

    def _apply_local_filters(self) -> None:
        rows = list(self._queue)
        if self._severity_tab != "all":
            rows = [
                r
                for r in rows
                if (r.severity or severity_for_score(r.composite_score))
                == self._severity_tab
            ]
        if self._driver_filter:
            rows = [
                r
                for r in rows
                if primary_driver(
                    r.anomaly_score, r.community_risk, r.network_signal, r.model_score
                )
                == self._driver_filter
            ]
        if self._network_only:
            rows = [r for r in rows if r.has_network_layer]
        self._queue = rows
        self._cursor = min(self._cursor, max(0, len(rows) - 1))

    def _render_posture(self) -> None:
        threat = self.app.store.threat_overview
        if threat is None:
            self.query_one("#threat-posture", Static).update("posture: loading")
            return
        text = Text(no_wrap=True, end="")
        text.append(" THREAT POSTURE ", Style(color="#000000", bgcolor=GOLD, bold=True))
        text.append("   critical ", Style(color=MUTED))
        text.append(f"{threat.critical_count:,}", Style(color=severity_colour("critical"), bold=True))
        text.append("   high ", Style(color=MUTED))
        text.append(f"{threat.high_count:,}", Style(color=severity_colour("high"), bold=True))
        text.append("   no-network evidence ", Style(color=MUTED))
        text.append(f"{threat.no_network_evidence_count:,}", Style(color=PINK, bold=True))
        text.append("   high-illicit communities ", Style(color=MUTED))
        text.append(f"{threat.high_illicit_community_count}", Style(color=YELLOW, bold=True))
        text.append("   tab ", Style(color=MUTED))
        text.append(f"[{self._severity_tab.upper()}]", Style(color=YELLOW, bold=True))
        if self._driver_filter:
            text.append("  driver ", Style(color=MUTED))
            text.append(
                self._driver_filter,
                Style(color=DRIVER_COLOURS[self._driver_filter], bold=True),
            )
        self.query_one("#threat-posture", Static).update(text)
        stack = self.query_one("#threat-stack", StackedBar)
        stack.critical = threat.critical_count
        stack.high = threat.high_count
        stack.medium = threat.medium_count
        stack.low = threat.low_count
        stack.refresh()

    def _render_queue(self) -> None:
        panel = self.query_one("#threat-queue", Static)
        panel.border_title = f"threat queue · top {len(self._queue)}"
        panel.border_subtitle = "j/k move · enter detail · g graph"
        width = max(40, panel.content_size.width or 70)
        text = Text(no_wrap=True, end="")
        text.append(
            f"  {'#':<4}{'tx':<12}{'sev':<6}{'score':<18}driver\n",
            Style(color=GOLD, bold=True),
        )
        for i, row in enumerate(self._queue):
            tier = row.severity or severity_for_score(row.composite_score)
            driver = primary_driver(
                row.anomaly_score, row.community_risk, row.network_signal, row.model_score
            )
            selected = i == self._cursor
            line = Text(no_wrap=True, end="")
            line.append("▶ " if selected else "  ", Style(color=YELLOW, bold=True))
            line.append(f"{row.rank:<4}", Style(color=MUTED))
            line.append(
                f"{row.elliptic_tx_id:<12}",
                Style(color=YELLOW if selected else TEXT, bold=selected),
            )
            line.append(f"{tier[:4].upper():<6}", Style(color=severity_colour(tier), bold=True))
            line.append(f"{row.composite_score:.2f} ", Style(color=TEXT))
            line.append_text(gradient_bar(row.composite_score, 12))
            line.append("  ")
            line.append(driver, Style(color=DRIVER_COLOURS.get(driver, TEXT), bold=True))
            if selected:
                line.pad_right(max(0, width - line.cell_len))
                line.stylize(Style(bgcolor="#2a2210"))
            text.append_text(line)
            text.append("\n")
        if not self._queue:
            text.append("(empty)", Style(color=MUTED))
        panel.update(text)

    def _render_drivers(self) -> None:
        panel = self.query_one("#threat-drivers", Static)
        panel.border_title = "driver breakdown · crit/high mean"
        rows = [
            r
            for r in self._queue
            if (r.severity or severity_for_score(r.composite_score))
            in {"critical", "high"}
        ]
        if not rows:
            # Fall back to whole queue for demo visibility.
            rows = self._queue
        if not rows:
            panel.update("(no rows)")
            return
        sums = {"MODEL": 0.0, "ANOMALY": 0.0, "COMMUNITY": 0.0, "NETWORK": 0.0}
        for r in rows:
            parts = weighted_parts(
                r.anomaly_score, r.community_risk, r.network_signal, r.model_score
            )
            for k, v in parts.items():
                sums[k] += v
        n = len(rows)
        means = [(k.lower(), sums[k] / n, DRIVER_COLOURS[k]) for k in sums]
        bar_w = max(8, (panel.content_size.width or 30) - 18)
        text = driver_bars(means, bar_w)
        total = sum(v for _, v, _ in means) or 1
        text.append("\n\nshare     ", Style(color=MUTED))
        for _, v, color in means:
            text.append("█" * max(1, round(v / total * bar_w)), Style(color=color))
        text.append("\n")
        lead = max(means, key=lambda m: m[1])
        text.append(f"{n} alerts · ", Style(color=MUTED))
        text.append(f"{lead[0]} leads", Style(color=lead[2], bold=True))
        panel.update(text)

    def _selected(self) -> AlertSummary | None:
        if not self._queue:
            return None
        return self._queue[self._cursor]

    def _render_signals(self) -> None:
        row = self._selected()
        panel = self.query_one("#threat-signals", Static)
        panel.border_title = "signals"
        if row is None:
            panel.update("(no selection)")
            return
        panel.border_subtitle = f"tx {row.elliptic_tx_id}"
        try:
            detail = self.app.store.provider.alert_detail(row.elliptic_tx_id)
        except ProviderError:
            panel.update("(unavailable)")
            return
        chips: list[tuple[str, bool]] = []
        for item in detail.evidence_items:
            label = item.label.lower()
            chip = None
            modeled = item.provenance == "modeled"
            if "illicit" in label and item.value not in {"unlabeled", "0", "0.0"}:
                chip = "RISKY COMMUNITY"
            elif "degree" in label:
                chip = "HIGH DEGREE"
            elif "pagerank" in label:
                chip = "HIGH PAGERANK"
            elif "country" in label:
                chip = "MULTI-COUNTRY IP"
            elif "tor" in label:
                chip = "TOR-EXIT ASN"
            elif "hosting" in label:
                chip = "HOSTING ASN"
            if chip:
                chips.append((chip, modeled))
        if not chips:
            panel.update(detail.evidence_text)
            return
        text = Text(end="")
        palette = (YELLOW, SALMON, CHROME, PINK)
        for i, (chip, modeled) in enumerate(chips):
            label = f" ~{chip} " if modeled else f" {chip} "
            text.append(
                label,
                Style(color="#000000", bgcolor=palette[i % len(palette)], bold=True),
            )
            text.append("  ")
        text.append("\n\n")
        text.append("~ modeled   ", Style(color=MUTED, italic=True))
        text.append("plain = real evidence", Style(color=MUTED))
        panel.update(text)

    def _render_coverage(self) -> None:
        panel = self.query_one("#threat-coverage", Static)
        panel.border_title = "coverage blind spots"
        top = self._queue[:25] if self._queue else []
        # Prefer full top-25 from provider for blind-spot stats.
        try:
            page = self.app.store.provider.alerts(AlertQuery(limit=25))
            top = page.items
        except ProviderError:
            pass
        n = max(1, len(top))
        no_net = sum(1 for r in top if not r.has_network_layer)
        no_syn = sum(1 for r in top if not r.has_synthetic_layer)
        text = Text(no_wrap=True, end="")
        for label, count, color in (
            ("no network  ", no_net, SALMON),
            ("no synthetic", no_syn, PINK),
        ):
            text.append(f"{label} ", Style(color=MUTED))
            text.append_text(hbar(count / n, 16, color))
            text.append(f" {count}", Style(color=color, bold=True))
            text.append(f"/{n} top\n", Style(color=MUTED))
        if no_net > 0:
            text.append("\n")
            text.append("! ", Style(color=YELLOW, bold=True))
            text.append(CAVEAT, Style(color=YELLOW, italic=True))
        panel.update(text)

    def _render_timeline(self) -> None:
        threat = self.app.store.threat_overview
        panel = self.query_one("#threat-timeline", Static)
        if threat is None or not threat.alerts_per_timestep:
            panel.display = False
            return
        panel.display = True
        series = threat.alerts_per_timestep
        peak_ts = max(series, key=series.get)
        keys = sorted(series)
        panel.border_title = "alerts per timestep"
        panel.border_subtitle = f"peak t{peak_ts} · {series[peak_ts]}"
        width = max(10, panel.content_size.width or 49)
        values = [
            float(series[keys[min(len(keys) - 1, i * len(keys) // width)]])
            for i in range(width)
        ]
        height = max(2, (panel.content_size.height or 5) - 1)
        chart = column_chart(values, height)
        first, last = f"t{keys[0]}", f"t{keys[-1]}"
        chart.append("\n")
        chart.append(first, Style(color=MUTED))
        chart.append(" " * max(1, width - len(first) - len(last)))
        chart.append(last, Style(color=MUTED))
        panel.update(chart)

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key in {"down", "j"}:
            if self._queue:
                self._cursor = min(len(self._queue) - 1, self._cursor + 1)
                self._render_queue()
                self._render_signals()
                event.stop()
        elif event.key in {"up", "k"}:
            if self._queue:
                self._cursor = max(0, self._cursor - 1)
                self._render_queue()
                self._render_signals()
                event.stop()

    def action_open_detail(self) -> None:
        row = self._selected()
        if row is None:
            return
        self.app.store.select_tx(row.elliptic_tx_id)
        self.app.push_screen(AlertDetailScreen(elliptic_tx_id=row.elliptic_tx_id))

    def action_open_graph(self) -> None:
        row = self._selected()
        if row is None:
            return
        self.app.store.select_tx(row.elliptic_tx_id)
        self.app.switch_mode("graph")

    def action_filter_anomaly(self) -> None:
        self._driver_filter = None if self._driver_filter == "ANOMALY" else "ANOMALY"
        self.refresh_view()

    def action_filter_community(self) -> None:
        self._driver_filter = None if self._driver_filter == "COMMUNITY" else "COMMUNITY"
        self.refresh_view()

    def action_filter_network_driver(self) -> None:
        self._driver_filter = None if self._driver_filter == "NETWORK" else "NETWORK"
        self.refresh_view()

    def action_toggle_network(self) -> None:
        self._network_only = not self._network_only
        self.refresh_view()

    def action_refresh(self) -> None:
        try:
            self.app.store.threat_overview = self.app.store.provider.threat_overview()
            self.app.store.communities = self.app.store.provider.top_communities(25)
            self.app.store.charts = self.app.store.provider.stats_charts()
        except ProviderError:
            pass
        self.refresh_view()

    def action_tab_all(self) -> None:
        self._severity_tab = "all"
        self.refresh_view()

    def action_tab_critical(self) -> None:
        self._severity_tab = "critical"
        self.refresh_view()

    def action_tab_high(self) -> None:
        self._severity_tab = "high"
        self.refresh_view()

    def action_tab_medium(self) -> None:
        self._severity_tab = "medium"
        self.refresh_view()
