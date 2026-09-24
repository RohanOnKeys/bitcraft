"""Threat detection screen: what to look at first, and why."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from tui.helpers.drivers import primary_driver, weighted_parts
from tui.helpers.format import score_bar
from tui.helpers.severity import severity_for_score
from tui.providers.models import AlertQuery, AlertSummary, ProviderError
from tui.screens.alert_detail import AlertDetailScreen
from tui.widgets.community_table import CommunityTable
from tui.widgets.header_bar import HeaderBar
from tui.widgets.stacked_bar import StackedBar

CAVEAT = "No network evidence is not the same as low risk"


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
                yield Static("", id="threat-queue")
                yield Static("", id="threat-drivers")
                yield CommunityTable(id="threat-communities")
            yield Static("", id="threat-signals")
            yield Static("", id="threat-coverage")
            yield Static("", id="threat-timeline")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()

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
                if primary_driver(r.anomaly_score, r.community_risk, r.network_signal)
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
        self.query_one("#threat-posture", Static).update(
            f"posture  critical={threat.critical_count}  "
            f"no-network={threat.no_network_evidence_count}  "
            f"high-illicit communities={threat.high_illicit_community_count}"
        )
        stack = self.query_one("#threat-stack", StackedBar)
        stack.critical = threat.critical_count
        stack.high = threat.high_count
        stack.medium = threat.medium_count
        stack.low = threat.low_count
        stack.refresh()

    def _render_queue(self) -> None:
        lines = ["threat queue (top 25)", "rank  tx           sev   score      driver"]
        for i, row in enumerate(self._queue):
            tier = row.severity or severity_for_score(row.composite_score)
            driver = primary_driver(
                row.anomaly_score, row.community_risk, row.network_signal
            )
            marker = ">" if i == self._cursor else " "
            lines.append(
                f"{marker}{row.rank:<5} {row.elliptic_tx_id:<12} "
                f"{tier[:4].upper():<5} {row.composite_score:.2f} "
                f"{score_bar(row.composite_score, 8)}  {driver}"
            )
        if not self._queue:
            lines.append("(empty)")
        self.query_one("#threat-queue", Static).update("\n".join(lines))

    def _render_drivers(self) -> None:
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
            self.query_one("#threat-drivers", Static).update("drivers\n(no rows)")
            return
        sums = {"ANOMALY": 0.0, "COMMUNITY": 0.0, "NETWORK": 0.0}
        for r in rows:
            parts = weighted_parts(r.anomaly_score, r.community_risk, r.network_signal)
            for k, v in parts.items():
                sums[k] += v
        n = len(rows)
        lines = ["driver breakdown (crit/high mean)"]
        for key in ("ANOMALY", "COMMUNITY", "NETWORK"):
            mean = sums[key] / n
            lines.append(f"{key:<10} {mean:.3f} {score_bar(mean, 12)}")
        self.query_one("#threat-drivers", Static).update("\n".join(lines))

    def _selected(self) -> AlertSummary | None:
        if not self._queue:
            return None
        return self._queue[self._cursor]

    def _render_signals(self) -> None:
        row = self._selected()
        panel = self.query_one("#threat-signals", Static)
        if row is None:
            panel.update("signals\n(no selection)")
            return
        try:
            detail = self.app.store.provider.alert_detail(row.elliptic_tx_id)
        except ProviderError:
            panel.update("signals\n(unavailable)")
            return
        if not detail.evidence_items:
            panel.update(f"signals\n{detail.evidence_text}")
            return
        chips: list[str] = []
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
                chips.append(f"~{chip}" if modeled else chip)
        panel.update("signals\n" + ("  ".join(chips) if chips else detail.evidence_text))

    def _render_coverage(self) -> None:
        top = self._queue[:25] if self._queue else []
        # Prefer full top-25 from provider for blind-spot stats.
        try:
            page = self.app.store.provider.alerts(AlertQuery(limit=25))
            top = page.items
        except ProviderError:
            pass
        no_net = sum(1 for r in top if not r.has_network_layer)
        no_syn = sum(1 for r in top if not r.has_synthetic_layer)
        lines = [
            "coverage blind spots",
            f"top-25 lacking network evidence: {no_net}",
            f"top-25 lacking synthetic layer: {no_syn}",
        ]
        if no_net > 0:
            lines.append(CAVEAT)
        self.query_one("#threat-coverage", Static).update("\n".join(lines))

    def _render_timeline(self) -> None:
        threat = self.app.store.threat_overview
        panel = self.query_one("#threat-timeline", Static)
        if threat is None or not threat.alerts_per_timestep:
            panel.display = False
            return
        panel.display = True
        series = threat.alerts_per_timestep
        peak_ts = max(series, key=series.get)
        max_v = max(series.values()) or 1
        # Compact sparkline across sorted timesteps.
        keys = sorted(series)
        bars = []
        glyphs = " .:-=+*#%@"
        for k in keys:
            idx = int(series[k] / max_v * (len(glyphs) - 1))
            bars.append(glyphs[idx])
        panel.update(
            f"timeline  peak timestep={peak_ts} ({series[peak_ts]})\n"
            + "".join(bars)
        )

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
