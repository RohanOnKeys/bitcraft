"""Splash screen: brand-first landing with the ASCII logo."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from tui.widgets.logo import Logo


class SplashScreen(Screen):
    """First screen on launch. Enter opens the dashboard."""

    BINDINGS = [
        ("enter", "enter_app", "Enter"),
        ("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="splash"):
            yield Static("", id="splash-spacer-top")
            yield Logo(show_tagline=True, id="splash-logo")
            # markup=False so literal [ Enter ] / [ Q ] are not eaten by Rich.
            yield Static(
                "\n[ Enter ]  open dashboard    [ Q ]  quit",
                id="splash-hint",
                markup=False,
            )
            yield Static("", id="splash-spacer-bottom")
        yield Footer()

    def action_enter_app(self) -> None:
        """Leave the splash and open the investigation dashboard."""
        self.app.enter_from_splash()
