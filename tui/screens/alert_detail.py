"""Alert detail screen: scores, evidence, coverage (populated from provider)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
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
from tui.widgets.header_bar import HeaderBar
from tui.widgets.panel_state import PanelState


class AlertDetailScreen(Screen):
    """Full detail view for one alert, backed by the store provider."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("d", "app.show_dashboard", "Dashboard"),
        ("g", "open_graph", "Graph"),
    ]

    def __init__(self, elliptic_tx_id: int) -> None:
        super().__init__()
        self.elliptic_tx_id = elliptic_tx_id

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        with Vertical(id="alert-detail"):
            yield PanelState(id="detail-state", message="Loading alert...")
            yield Static("", id="detail-body")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._load, exclusive=True, thread=True)

    def _load(self) -> None:
        store = self.app.store
        try:
            detail = store.provider.alert_detail(self.elliptic_tx_id)
        except ProviderError as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._show_detail, detail)

    def _show_error(self, message: str) -> None:
        self.query_one("#detail-state", PanelState).set_error(message)
        self.query_one("#detail-body", Static).update("")

    def _show_detail(self, detail) -> None:  # type: ignore[no-untyped-def]
        self.query_one("#detail-state").display = False
        tier = detail.severity or severity_for_score(detail.composite_score)
        wa = ANOMALY_WEIGHT * detail.anomaly_score
        wc = COMMUNITY_WEIGHT * detail.community_risk
        wn = NETWORK_WEIGHT * detail.network_signal
        net = network_cell(detail.has_network_layer, detail.network_signal)
        lines = [
            f"Alert  tx={detail.elliptic_tx_id}  rank={detail.rank}  sev={tier}",
            f"[{self.app.store.source_label}]",
            "",
            f"composite   {detail.composite_score:.3f}  {score_bar(detail.composite_score)}",
            f"anomaly     {detail.anomaly_score:.3f}  (x0.60 -> {wa:.3f})",
            f"community   {detail.community_risk:.3f}  (x0.25 -> {wc:.3f})",
            f"network     {net}  (x0.15 -> {wn:.3f})",
            "",
            f"synthetic layer  {'yes' if detail.has_synthetic_layer else 'no'}",
            f"network layer    {'yes' if detail.has_network_layer else 'no'}",
            "",
            "evidence",
            detail.evidence_text,
            "",
        ]
        if detail.evidence_items:
            for item in detail.evidence_items:
                badge = "[REAL]" if item.provenance == "real" else "[MODELED]"
                lines.append(f"  {badge} {item.label}: {item.value}")
        if detail.shap_reasons:
            lines.append("")
            lines.append("SHAP (feature index only, features are anonymized)")
            for s in detail.shap_reasons:
                lines.append(
                    f"  feature_{s.feature_index:>3}  {s.contribution:+.3f}  "
                    f"{score_bar(abs(s.contribution), 8)}"
                )
        self.query_one("#detail-body", Static).update("\n".join(lines))

    def action_open_graph(self) -> None:
        """Switch to graph mode (selected tx remembered in the store)."""
        self.app.store.select_tx(self.elliptic_tx_id)
        self.app.switch_mode("graph")
