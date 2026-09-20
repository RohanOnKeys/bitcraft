"""Standalone graph explorer screen: full link-analysis view."""

from textual.screen import Screen
from textual.widgets import Footer, Header

from tui.widgets.graph_view import GraphView


class GraphExplorerScreen(Screen):
    """Full-page pan/navigate graph view, colored by score or community."""

    def compose(self):
        yield Header()
        yield GraphView(id="graph-view")
        yield Footer()
