"""Alert detail screen: scores, evidence, coverage (populated from provider)."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from bitcraft.helpers.format import network_cell
from bitcraft.helpers.severity import severity_for_score
from bitcraft.helpers.drivers import (
    ANOMALY_WEIGHT,
    COMMUNITY_WEIGHT,
    MODEL_WEIGHT,
    NETWORK_WEIGHT,
)
from bitcraft.providers.models import ProviderError
from bitcraft.widgets.chart_panel import (
    DRIVER_COLOURS,
    driver_bars,
    score_gauge,
    severity_colour,
)
from bitcraft.widgets.chart import CHROME, MUTED, PINK, SALMON, TEXT, YELLOW, hbar
from bitcraft.widgets.graph_view import GraphView
from bitcraft.widgets.header_bar import HeaderBar
from bitcraft.widgets.panel_state import PanelState


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
        with Horizontal(id="alert-detail"):
            with Vertical(id="detail-main"):
                yield PanelState(id="detail-state", message="Loading alert...")
                yield Static("", id="detail-body", classes="panel")
            with Vertical(id="detail-side"):
                yield GraphView(
                    self.elliptic_tx_id, clusters=4, id="detail-graph", classes="panel"
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#detail-graph").border_title = "neighbourhood"
        self.query_one("#detail-graph").border_subtitle = f"tx {self.elliptic_tx_id}"
        self._fit()
        self.run_worker(self._load, exclusive=True, thread=True)

    def on_resize(self, event) -> None:  # type: ignore[no-untyped-def]
        self._fit()

    def _fit(self) -> None:
        wide = self.size.width >= 140
        self.query_one("#detail-side").styles.width = 58 if wide else 44
        self.query_one("#detail-side").display = self.size.width >= 100

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
        wm = MODEL_WEIGHT * (detail.model_score or 0.0)
        wa = ANOMALY_WEIGHT * detail.anomaly_score
        wc = COMMUNITY_WEIGHT * detail.community_risk
        wn = NETWORK_WEIGHT * detail.network_signal
        net = network_cell(detail.has_network_layer, detail.network_signal)
        body = self.query_one("#detail-body", Static)
        body.border_title = f"alert · tx {detail.elliptic_tx_id}"
        bar_w = max(12, min(40, (body.content_size.width or 60) - 30))

        def label(name: str) -> None:
            text.append(f"{name:<12}", Style(color=MUTED))

        def heading(name: str) -> None:
            text.append(f"\n{name}\n", Style(color=YELLOW, bold=True, underline=True))

        text = Text(end="")
        text.append(f" {tier.upper()} ", Style(color="#000000", bgcolor=severity_colour(tier), bold=True))
        text.append("  rank ", Style(color=MUTED))
        text.append(f"#{detail.rank}", Style(color=YELLOW, bold=True))
        text.append("  tx ", Style(color=MUTED))
        text.append(f"{detail.elliptic_tx_id}\n", Style(color=TEXT, bold=True))
        heading("composite score")
        label("composite")
        text.append_text(score_gauge(detail.composite_score, bar_w + 12))
        text.append("\n")
        heading("drivers (weighted)")
        text.append_text(driver_bars(
            [
                ("risk model", wm, DRIVER_COLOURS["MODEL"]),
                ("anomaly", wa, DRIVER_COLOURS["ANOMALY"]),
                ("community", wc, DRIVER_COLOURS["COMMUNITY"]),
                ("network", wn, DRIVER_COLOURS["NETWORK"]),
            ],
            bar_w,
        ))
        text.append("\n")
        label("raw")
        if detail.model_score is not None:
            text.append(f"model {detail.model_score:.3f} · ", Style(color=TEXT))
        text.append(f"anomaly {detail.anomaly_score:.3f} · community "
                    f"{detail.community_risk:.3f} · network {net}\n", Style(color=TEXT))
        label("layers")
        for name, on in (("synthetic", detail.has_synthetic_layer), ("network", detail.has_network_layer)):
            text.append(f" {name} ", Style(color="#000000", bgcolor=YELLOW if on else "#3a3228", bold=True))
            text.append(" ")
        text.append("\n")
        meta = detail.metadata
        if meta is not None:
            heading("network ↔ blockchain metadata")
            label("txid")
            text.append(f"{meta.txid}\n", Style(color=YELLOW))
            label("source")
            src_style = Style(color=SALMON if meta.tor else TEXT, bold=True)
            text.append(f"{meta.src_ip}:{meta.src_port}", src_style)
            text.append(f"  {meta.src_country or '--'}  {meta.src_asn_org or ''}", Style(color=MUTED))
            if meta.tor:
                text.append("  TOR", Style(color="#000000", bgcolor=PINK, bold=True))
            text.append("\n")
            label("peer")
            text.append(f"{meta.dst_ip}:{meta.dst_port}", Style(color=TEXT))
            text.append(f"  {meta.dst_country or '--'}\n", Style(color=MUTED))
            label("shape")
            text.append(
                f"{meta.n_inputs} in / {meta.n_outputs} out · {meta.total_in_btc:.4f} BTC · fee {meta.fee:.8f}"
                f" · {meta.script_type or '?'}\n",
                Style(color=TEXT),
            )
            if meta.peel_chain_len >= 2:
                label("peel chain")
                text.append(f"step {meta.peel_chain_len}\n", Style(color=SALMON, bold=True))
            label("wallet")
            wallet = f"{meta.entity_id}"
            if meta.entity_rank is not None:
                wallet += f"  rank {meta.entity_rank}  risk {meta.entity_risk or 0:.2f}"
            text.append(wallet + "  (press w for wallets)\n", Style(color=CHROME, bold=True))
            label("meta score")
            text.append(f"{meta.metadata_score:.3f}\n", Style(color=YELLOW, bold=True))
        heading("evidence")
        text.append(detail.evidence_text + "\n", Style(color=TEXT))
        for item in detail.evidence_items or []:
            real = item.provenance == "real"
            text.append(" REAL " if real else " MODELED ",
                        Style(color="#000000", bgcolor=YELLOW if real else PINK, bold=True))
            text.append(f" {item.label}: ", Style(color=MUTED))
            text.append(f"{item.value}\n", Style(color=TEXT, bold=True))
        if detail.shap_reasons:
            heading("SHAP (feature index only, features are anonymized)")
            peak = max(abs(r.contribution) for r in detail.shap_reasons) or 1
            for r in detail.shap_reasons:
                color = SALMON if r.contribution >= 0 else PINK
                name = r.feature or f"feature_{r.feature_index}"
                text.append(f"{name[:18]:<19}", Style(color=MUTED))
                text.append(f"{r.contribution:+.3f} ", Style(color=color, bold=True))
                text.append_text(hbar(abs(r.contribution) / peak, bar_w, color))
                text.append("\n")
        body.update(text)

    def action_open_graph(self) -> None:
        """Switch to graph mode (selected tx remembered in the store)."""
        self.app.store.select_tx(self.elliptic_tx_id)
        self.app.switch_mode("graph")
