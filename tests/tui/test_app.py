"""Smoke tests for the BitCraft TUI shell and ASCII logo."""

import pytest

from tui.app import BitCraftApp
from tui.providers.demo_provider import DemoProvider
from tui.screens.boot import BootScreen
from tui.screens.dashboard import DashboardScreen
from tui.screens.graph_explorer import GraphExplorerScreen
from tui.screens.splash import SplashScreen
from tui.store import Store
from tui.widgets.logo import BITCRAFT_LOGO, BITCRAFT_TAGLINE


def test_logo_is_pure_ascii() -> None:
    """Logo must render on every terminal; no Unicode block characters."""
    assert BITCRAFT_LOGO.isascii()
    assert "BitCraft" not in BITCRAFT_LOGO  # wordmark is the glyphs themselves
    assert "Bitcoin" in BITCRAFT_TAGLINE


async def _wait_for_dashboard(app: BitCraftApp, pilot, ticks: int = 200) -> None:
    """Advance past boot until the dashboard mode screen is active."""
    for _ in range(ticks):
        if isinstance(app.screen, DashboardScreen) and app.store.boot_complete:
            return
        if isinstance(app.screen, BootScreen):
            await pilot.pause(0.05)
            continue
        await pilot.pause(0.05)
    raise AssertionError(f"dashboard not reached; screen={type(app.screen).__name__}")


@pytest.mark.asyncio
async def test_splash_to_dashboard_to_graph() -> None:
    """Core navigation: splash -> boot -> dashboard -> graph -> dashboard."""
    app = BitCraftApp(
        store=Store(
            provider=DemoProvider(simulate_latency=False),
            is_demo=True,
            fast_boot=True,
            boot_log=["test"],
        )
    )
    async with app.run_test(size=(120, 40)) as pilot:
        assert isinstance(app.screen, SplashScreen)
        await pilot.press("enter")
        await _wait_for_dashboard(app, pilot)
        assert isinstance(app.screen, DashboardScreen)
        await pilot.press("g")
        assert isinstance(app.screen, GraphExplorerScreen)
        await pilot.press("d")
        assert isinstance(app.screen, DashboardScreen)
