"""Alert detail panel: scores, SHAP, and evidence for one transaction."""

from textual.widget import Widget


class AlertDetailPanel(Widget):
    """Full detail view for one alert, backed by GET /alerts/{tx_id}.

    Synthetic-layer values in the evidence must render with the
    "modeled" badge style (see tui/theme.tcss), never as observed facts.
    """

    def __init__(self, elliptic_tx_id: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.elliptic_tx_id = elliptic_tx_id

    def render(self) -> str:
        return f"Alert detail for {self.elliptic_tx_id}: not yet wired to the API."
