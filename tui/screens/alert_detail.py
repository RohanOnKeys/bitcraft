"""Alert detail screen: scores, SHAP, evidence, and an embedded mini-graph."""

from textual.screen import Screen
from textual.widgets import Footer, Header

from tui.widgets.alert_detail_panel import AlertDetailPanel
from tui.widgets.graph_view import GraphView


class AlertDetailScreen(Screen):
    """Full detail view for one alert, backed by GET /alerts/{tx_id}."""

    def __init__(self, elliptic_tx_id: int) -> None:
        super().__init__()
        self.elliptic_tx_id = elliptic_tx_id

    def compose(self):
        yield Header()
        yield AlertDetailPanel(self.elliptic_tx_id, id="alert-detail-panel")
        yield GraphView(self.elliptic_tx_id, id="graph-view")
        yield Footer()
