"""Wallets screen: ranked wallet (address cluster) alerts and their evidence.

Left: wallets ranked by risk. Right: why the selected wallet was flagged,
and its link graph (wallet -> transactions -> addresses / IPs).
Bottom: its riskiest transactions with IP:port, GeoIP country and ASN.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from tui.providers.models import ProviderError, WalletDetail, WalletPage
from tui.widgets.chart_panel import score_gauge, severity_colour
from tui.widgets.chart import CHROME, GOLD, MUTED, PINK, SALMON, TEXT, YELLOW, hbar
from tui.widgets.graph_view import GraphView, network_from_link_graph
from tui.widgets.header_bar import HeaderBar

PAGE = 200
WIDE_SIDE_MIN_WIDTH = 150


class WalletTable(DataTable):
    """Ranked wallets."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("#", "wallet", "sev", "risk", "addrs", "txs", "IPs", "ctry", "tor", "peel", "alerts")

    def load(self, page: WalletPage) -> None:
        self.clear()
        for w in page.items:
            self.add_row(
                str(w.rank),
                str(w.entity_id),
                w.severity[:4].upper(),
                f"{w.risk_score:.2f}",
                str(w.n_addresses),
                str(w.n_txs),
                str(w.distinct_src_ips),
                str(w.distinct_src_countries),
                f"{w.tor_share:.0%}",
                str(w.peel_chain_max),
                str(w.linked_alerts) if w.linked_alerts else "",
                key=str(w.entity_id),
            )


class WalletsScreen(Screen):
    """Wallet alerts, evidence and link analysis."""

    BINDINGS = [("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        with Vertical(id="wallets"):
            yield Static("", id="wallet-posture")
            with Horizontal(id="wallet-body"):
                yield WalletTable(id="wallet-table", classes="panel")
                with Vertical(id="wallet-side"):
                    yield Static("", id="wallet-detail", classes="panel")
                    yield GraphView(id="wallet-graph", classes="panel")
            yield Static("", id="wallet-txs", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#wallet-table").border_title = "wallet alerts · common-input clusters"
        self.query_one("#wallet-detail").border_title = "why flagged"
        self.query_one("#wallet-graph").border_title = "link graph · wallet → tx → address / IP"
        self.query_one("#wallet-txs").border_title = "riskiest transactions · network ↔ blockchain"
        self._fit()
        self.action_refresh()

    def on_resize(self, event) -> None:  # type: ignore[no-untyped-def]
        self._fit()

    def _fit(self) -> None:
        wide = self.size.width >= WIDE_SIDE_MIN_WIDTH
        self.query_one("#wallet-side").styles.width = 60 if wide else 52

    def action_refresh(self) -> None:
        def work() -> None:
            try:
                page = self.app.store.provider.wallets(0, PAGE)
            except (ProviderError, AttributeError) as exc:
                self.app.call_from_thread(self._show_error, str(exc))
                return
            self.app.call_from_thread(self._show_page, page)

        self.run_worker(work, thread=True, exclusive=True, group="wallets")

    def _show_error(self, message: str) -> None:
        self.query_one("#wallet-posture", Static).update(
            Text(f" wallets unavailable: {message}", Style(color=SALMON))
        )

    def _show_page(self, page: WalletPage) -> None:
        table = self.query_one("#wallet-table", WalletTable)
        table.load(page)
        table.focus()
        crit = sum(1 for w in page.items if w.severity == "critical")
        tor = sum(1 for w in page.items if w.tor_share >= 0.2)
        multi = sum(1 for w in page.items if w.distinct_src_countries >= 3)
        text = Text(no_wrap=True, end="")
        text.append(" WALLETS ", Style(color="#000000", bgcolor=GOLD, bold=True))
        for label, value, colour in (
            ("flagged", f"{page.total:,}", YELLOW),
            ("critical in view", str(crit), severity_colour("critical")),
            ("Tor-heavy", str(tor), PINK),
            ("multi-country", str(multi), CHROME),
        ):
            text.append(f"   {label} ", Style(color=MUTED))
            text.append(value, Style(color=colour, bold=True))
        self.query_one("#wallet-posture", Static).update(text)
        if page.items:
            self._select(page.items[0].entity_id)

    def on_data_table_row_highlighted(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.data_table.id == "wallet-table" and event.row_key is not None:
            self._select(int(str(event.row_key.value)))

    def _select(self, entity_id: int) -> None:
        def work() -> None:
            provider = self.app.store.provider
            try:
                detail = provider.wallet_detail(entity_id)
                graph = provider.wallet_graph(entity_id)
            except (ProviderError, AttributeError):
                return
            self.app.call_from_thread(self._show_detail, detail, graph)

        self.run_worker(work, thread=True, exclusive=True, group="wallet-detail")

    def _show_detail(self, detail: WalletDetail, graph) -> None:  # type: ignore[no-untyped-def]
        w = detail.summary
        panel = self.query_one("#wallet-detail", Static)
        panel.border_subtitle = f"wallet {w.entity_id} · rank {w.rank}"
        bar_w = max(10, (panel.content_size.width or 50) - 22)
        text = Text(end="")
        text.append(f" {w.severity.upper()} ", Style(color="#000000", bgcolor=severity_colour(w.severity), bold=True))
        text.append("  confidence ", Style(color=MUTED))
        text.append_text(score_gauge(w.risk_score, bar_w))
        text.append("\n")
        text.append(detail.evidence_text + "\n", Style(color=TEXT))
        for item in detail.evidence_items[:8]:
            real = item.provenance == "real"
            text.append(" REAL " if real else " MOD  ", Style(color="#000000", bgcolor=YELLOW if real else PINK, bold=True))
            text.append(f" {item.label}: ", Style(color=MUTED))
            text.append(f"{item.value}\n", Style(color=TEXT, bold=True))
        if detail.countries:
            text.append("countries ", Style(color=MUTED))
            text.append(" ".join(detail.countries[:10]) + "\n", Style(color=CHROME, bold=True))
        text.append("Tor share ", Style(color=MUTED))
        text.append_text(hbar(w.tor_share, 16, PINK))
        text.append(f" {w.tor_share:.0%}", Style(color=PINK, bold=True))
        panel.update(text)

        view = self.query_one("#wallet-graph", GraphView)
        view.set_network(network_from_link_graph(graph))
        view.border_subtitle = f"{len(graph.nodes)} nodes · {len(graph.edges)} links"

        txs = Text(no_wrap=True, end="")
        txs.append(
            f"{'txid':<12}{'src ip:port':<24}{'ctry':<6}{'asn':<22}{'dst port':<9}{'in/out':<8}{'BTC':>11}  score\n",
            Style(color=GOLD, bold=True),
        )
        for t in detail.transactions[:6]:
            colour = SALMON if t.tor else TEXT
            txs.append(f"{t.txid[:10]:<12}", Style(color=YELLOW))
            txs.append(f"{t.src_ip + ':' + str(t.src_port):<24}", Style(color=colour, bold=t.tor))
            txs.append(f"{(t.src_country or '--'):<6}", Style(color=CHROME))
            txs.append(f"{(t.src_asn_org or '-')[:20]:<22}", Style(color=MUTED))
            txs.append(f"{t.dst_port:<9}", Style(color=SALMON if t.dst_port != 8333 else MUTED))
            txs.append(f"{t.n_inputs}/{t.n_outputs:<6}", Style(color=TEXT))
            txs.append(f"{t.total_in_btc:>11.4f}  ", Style(color=TEXT))
            txs.append(f"{t.metadata_score:.2f}\n", Style(color=severity_colour("critical") if t.metadata_score >= 0.8 else YELLOW, bold=True))
        self.query_one("#wallet-txs", Static).update(txs)
