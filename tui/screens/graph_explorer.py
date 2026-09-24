"""Standalone graph explorer screen: full link-analysis view."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static

from tui.widgets.graph_view import GraphView
from tui.widgets.header_bar import HeaderBar


class GraphExplorerScreen(Screen):
    """Full-page pan/navigate graph view, colored by score or community."""

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        yield Static("Graph Explorer", classes="accent", id="graph-title")
        yield GraphView(id="graph-view")
        yield Footer()
