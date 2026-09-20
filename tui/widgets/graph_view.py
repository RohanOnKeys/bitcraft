"""Text-rendered link-analysis graph view."""

from textual.widget import Widget


class GraphView(Widget):
    """Pan/navigate graph view, colored by score or community.

    Rendered as text inside the terminal; backed by GET /graph/{tx_id}.
    With no elliptic_tx_id given, acts as the full graph explorer.
    """

    def __init__(self, elliptic_tx_id: int | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.elliptic_tx_id = elliptic_tx_id

    def render(self) -> str:
        return "Graph view: not yet wired to the API."
