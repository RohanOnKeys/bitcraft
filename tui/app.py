"""BitCraft TUI entry point.

Terminal interface built with Textual. Reads pre-computed alert, graph,
and community data from the FastAPI backend only; no ML code runs here.
See docs/tui_design.md for the screen layout and theme, and
plans/plan.md section 11 for the architecture this implements.
"""

from textual.app import App

from tui.screens.dashboard import DashboardScreen


class BitCraftApp(App):
    """Root Textual application."""

    CSS_PATH = "theme.tcss"
    TITLE = "BitCraft"

    def on_mount(self) -> None:
        """Push the dashboard as the initial screen."""
        self.push_screen(DashboardScreen())


if __name__ == "__main__":
    BitCraftApp().run()
