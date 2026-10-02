"""BitCraft TUI entry point.

Terminal interface built with Textual. Reads pre-computed alert, graph,
and community data through a swappable DataProvider (demo or FastAPI).
No ML code runs here. See docs/tui_design.md and plans/plan.md section 11.
"""

from __future__ import annotations

import argparse
import os
from typing import Optional

from textual.app import App, ScreenStackError
from textual.binding import Binding
from textual.theme import Theme

from bitcraft.api_client import DEFAULT_BASE_URL
from bitcraft.providers.demo_provider import DemoProvider
from bitcraft.providers.factory import create_provider, resolve_source
from bitcraft.screens.boot import BootScreen
from bitcraft.screens.dashboard import DashboardScreen
from bitcraft.screens.graph_explorer import GraphExplorerScreen
from bitcraft.screens.splash import SplashScreen
from bitcraft.screens.threat_detection import ThreatDetectionScreen
from bitcraft.screens.wallet import WalletsScreen
from bitcraft.store import Store


# Gold everywhere Textual would otherwise paint its default blue: table
# cursors, scrollbars, focus borders, footer keys, checkboxes, selections.
BITCRAFT_THEME = Theme(
    name="bitcraft",
    primary="#d4af37",
    secondary="#ffa700",
    accent="#ffd84d",
    warning="#ff8c42",
    error="#b3261e",
    success="#d4af37",
    foreground="#e6e6e6",
    background="#000000",
    surface="#050505",
    panel="#0d0b08",
    dark=True,
    variables={
        "block-cursor-background": "#d4af37",
        "block-cursor-foreground": "#000000",
        "block-cursor-text-style": "bold",
        "block-cursor-blurred-background": "#d4af37 45%",
        "block-cursor-blurred-foreground": "#000000",
        "block-hover-background": "#d4af37 12%",
        "scrollbar": "#d4af37 55%",
        "scrollbar-hover": "#e8c55a",
        "scrollbar-active": "#ffd84d",
        "scrollbar-background": "#0d0b08",
        "scrollbar-background-hover": "#0d0b08",
        "scrollbar-background-active": "#0d0b08",
        "scrollbar-corner-color": "#0d0b08",
        "footer-key-foreground": "#d4af37",
        "footer-foreground": "#7a7a7a",
        "footer-background": "#000000",
        "footer-description-foreground": "#9a9080",
        "input-cursor-background": "#d4af37",
        "input-cursor-foreground": "#000000",
        "input-selection-background": "#d4af37 35%",
        "screen-selection-background": "#d4af37 35%",
        "border": "#d4af37",
        "border-blurred": "#3a3020",
        "link-color": "#ffd84d",
    },
)


class BitCraftApp(App):
    """Root Textual application using modes for the main investigation screens.

    Flow: splash -> boot -> dashboard. Modes: dashboard, threats, graph.
    Detail screens push on top of the active mode.
    """

    CSS_PATH = "theme.tcss"
    TITLE = "BitCraft"
    MODES = {
        "dashboard": DashboardScreen,
        "graph": GraphExplorerScreen,
        "threats": ThreatDetectionScreen,
        "wallets": WalletsScreen,
    }
    DEFAULT_MODE = "dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("d", "show_dashboard", "Dashboard", priority=True),
        Binding("g", "show_graph", "Graph", priority=True),
        Binding("t", "show_threats", "Threats", priority=True),
        Binding("w", "show_wallets", "Wallets", priority=True),
        Binding("escape", "go_home", "Home", priority=True),
    ]

    def __init__(self, store: Optional[Store] = None) -> None:
        super().__init__()
        if store is None:
            store = Store(
                provider=DemoProvider(simulate_latency=False),
                is_demo=True,
                boot_log=["demo default"],
                fast_boot=True,
            )
        self.store = store
        self.register_theme(BITCRAFT_THEME)
        self.theme = "bitcraft"

    def clear_selection(self) -> None:
        """Ignore the startup window where the mode stack is still empty.

        Textual mounts the DEFAULT_MODE screen before registering its stack,
        and with eager tasks the dashboard's filter Inputs run their selection
        watcher (which calls this) inside that window. Textual only catches
        NoScreen here, so a real `app.run()` crashed with ScreenStackError.
        """
        try:
            super().clear_selection()
        except ScreenStackError:
            pass

    def on_mount(self) -> None:
        """Open on the brand splash above the default dashboard mode."""
        self.push_screen(SplashScreen())

    def _pop_overlays(self) -> None:
        """Pop pushed overlays until a mode screen is on top."""
        mode_types = (DashboardScreen, GraphExplorerScreen, ThreatDetectionScreen, WalletsScreen)
        while len(self.screen_stack) > 1 and not isinstance(self.screen, mode_types):
            self.pop_screen()

    def action_show_dashboard(self) -> None:
        """Switch to dashboard mode (ignored on splash)."""
        if isinstance(self.screen, (SplashScreen, BootScreen)):
            return
        self.switch_mode("dashboard")
        self._pop_overlays()

    def action_show_graph(self) -> None:
        """Switch to graph mode."""
        if isinstance(self.screen, (SplashScreen, BootScreen)):
            return
        self.switch_mode("graph")
        self._pop_overlays()

    def action_show_threats(self) -> None:
        """Switch to threats mode."""
        if isinstance(self.screen, (SplashScreen, BootScreen)):
            return
        self.switch_mode("threats")
        self._pop_overlays()

    def action_show_wallets(self) -> None:
        """Switch to wallets mode."""
        if isinstance(self.screen, (SplashScreen, BootScreen)):
            return
        self.switch_mode("wallets")
        self._pop_overlays()

    def action_go_home(self) -> None:
        """Return to the ASCII-logo splash above the current mode."""
        if isinstance(self.screen, SplashScreen):
            return
        if isinstance(self.screen, BootScreen):
            return
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(SplashScreen())

    def enter_from_splash(self) -> None:
        """Dismiss splash and open the boot loader."""
        if isinstance(self.screen, SplashScreen):
            self.pop_screen()
        self.push_screen(BootScreen())


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI flags for data source selection."""
    parser = argparse.ArgumentParser(description="BitCraft terminal interface")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Force the deterministic demo provider",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Force the FastAPI provider",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("BITCRAFT_API_URL", DEFAULT_BASE_URL),
        help=f"Backend base URL (default {DEFAULT_BASE_URL})",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    """Run the BitCraft terminal interface."""
    args = build_arg_parser().parse_args(argv)
    source = resolve_source(cli_demo=args.demo, cli_api=args.api)
    choice = create_provider(source=source, api_url=args.api_url)
    store = Store(
        provider=choice.provider,
        boot_log=list(choice.boot_log),
        is_demo=(choice.provider.source_label == "DEMO DATA"),
        fast_boot=False,
    )
    app = BitCraftApp(store=store)
    app.run()


if __name__ == "__main__":
    main()
