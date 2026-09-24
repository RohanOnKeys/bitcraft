"""BitCraft TUI entry point.

Terminal interface built with Textual. Reads pre-computed alert, graph,
and community data through a swappable DataProvider (demo or FastAPI).
No ML code runs here. See docs/tui_design.md and plans/plan.md section 11.
"""

from __future__ import annotations

import argparse
import os
from typing import Optional

from textual.app import App
from textual.binding import Binding

from tui.api_client import DEFAULT_BASE_URL
from tui.providers.demo_provider import DemoProvider
from tui.providers.factory import create_provider, resolve_source
from tui.screens.boot import BootScreen
from tui.screens.dashboard import DashboardScreen
from tui.screens.graph_explorer import GraphExplorerScreen
from tui.screens.splash import SplashScreen
from tui.screens.threat_detection import ThreatDetectionScreen
from tui.store import Store


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
    }
    DEFAULT_MODE = "dashboard"
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("d", "show_dashboard", "Dashboard", priority=True),
        Binding("g", "show_graph", "Graph", priority=True),
        Binding("t", "show_threats", "Threats", priority=True),
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

    def on_mount(self) -> None:
        """Open on the brand splash above the default dashboard mode."""
        self.push_screen(SplashScreen())

    def _pop_overlays(self) -> None:
        """Pop pushed overlays until a mode screen is on top."""
        mode_types = (DashboardScreen, GraphExplorerScreen, ThreatDetectionScreen)
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
