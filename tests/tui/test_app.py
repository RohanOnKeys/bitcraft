"""Smoke tests for the BitCraft TUI shell and ASCII logo."""

import pytest

from bitcraft.app import BitCraftApp
from bitcraft.providers.demo_provider import DemoProvider
from bitcraft.screens.boot import BootScreen
from bitcraft.screens.dashboard import DashboardScreen
from bitcraft.screens.graph_explorer import GraphExplorerScreen
from bitcraft.screens.splash import SplashScreen
from bitcraft.store import Store
from bitcraft.widgets.logo import BITCRAFT_LOGO, BITCRAFT_TAGLINE


def test_logo_is_solid_block_wordmark() -> None:
    """Logo is solid block letters with box-drawing shadows, six rows tall."""
    rows = BITCRAFT_LOGO.split("\n")
    assert len(rows) == 6
    assert "█" in BITCRAFT_LOGO
    assert set(BITCRAFT_LOGO) <= set("█╗╔╝╚║═ \n")
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


def test_real_run_reaches_threats_without_errors() -> None:
    """A real app.run() (not run_test) must start and navigate cleanly.

    run_test did not reproduce the startup ScreenStackError that the filter
    Inputs raised under Textual's eager tasks; only a real run did.
    """
    app = BitCraftApp(
        store=Store(
            provider=DemoProvider(simulate_latency=False),
            is_demo=True,
            fast_boot=True,
            boot_log=["test"],
        )
    )

    def script() -> None:
        app.set_timer(0.3, app.enter_from_splash)
        app.set_timer(1.5, app.action_show_threats)
        app.set_timer(2.0, app.action_show_dashboard)
        app.set_timer(2.5, app.exit)

    app.call_later(script)
    app.run(headless=True, size=(140, 42))
    assert app.return_code == 0
