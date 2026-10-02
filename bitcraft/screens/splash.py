"""Splash screen: brand-first landing with the ASCII logo."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from bitcraft.widgets.logo import Logo
from bitcraft.widgets.mascot import NATIVE_WIDTH, Mascot

# Below this height the frog would crowd out the logo and hint.
MASCOT_MIN_HEIGHT = 34


class SplashScreen(Screen):
    """First screen on launch. Enter opens the dashboard."""

    BINDINGS = [
        ("enter", "enter_app", "Enter"),
        ("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="splash"):
            yield Static("", id="splash-spacer-top")
            yield Mascot(
                "happy", art_width=NATIVE_WIDTH, idle=True, id="splash-mascot"
            )
            yield Logo(show_tagline=True, id="splash-logo")
            # markup=False so literal [ Enter ] / [ Q ] are not eaten by Rich.
            yield Static(
                "\n[ Enter ]  open dashboard    [ Q ]  quit",
                id="splash-hint",
                markup=False,
            )
            yield Static("", id="splash-spacer-bottom")
        yield Footer()

    def on_resize(self) -> None:
        # Downsampled frogs lose their faces, so hide rather than shrink.
        self.query_one("#splash-mascot", Mascot).display = (
            self.size.height >= MASCOT_MIN_HEIGHT
        )

    def action_enter_app(self) -> None:
        """Leave the splash and open the investigation dashboard."""
        self.app.enter_from_splash()
