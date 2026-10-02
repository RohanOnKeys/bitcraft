"""Tests for the frog mascot art, renderer, and mood wiring."""

import pytest

from tui.app import BitCraftApp
from tui.providers.demo_provider import DemoProvider
from tui.screens.dashboard import DashboardScreen
from tui.store import Store
from tui.widgets.mascot import (
    ASSET_DIR,
    HOP_HEADROOM,
    IDLE_MOODS,
    MOODS,
    Mascot,
    mascot_pixels,
    render_mascot,
)


def test_every_mood_has_art() -> None:
    """Each mood ships a PNG so no screen can ask for a missing frog."""
    for mood in MOODS:
        assert (ASSET_DIR / f"{mood}.png").is_file(), mood
    assert {"happy", "thinking", "panic"}.isdisjoint(IDLE_MOODS)


@pytest.mark.parametrize("width", [24, 28, 36])
def test_render_size_is_stable_across_moods_and_lifts(width: int) -> None:
    """Mood swaps and hops must never change the widget's footprint."""
    shapes = set()
    for mood in MOODS:
        for lift in range(HOP_HEADROOM + 1):
            lines = render_mascot(mood, width, lift).plain.split("\n")
            assert all(len(line) == width for line in lines)
            shapes.add(len(lines))
    assert len(shapes) == 1


def test_art_keeps_facial_features() -> None:
    """Downsampling keeps dark eye/mouth pixels instead of blurring to gold."""
    pixels = mascot_pixels("happy", 28)
    dark = [p for row in pixels for p in row if p is not None and max(p) <= 70]
    assert dark


def test_lift_raises_the_frog() -> None:
    """A full hop moves the art up; rest leaves the headroom on top."""
    rest = render_mascot("happy", 28, 0).plain.split("\n")
    up = render_mascot("happy", 28, HOP_HEADROOM).plain.split("\n")
    assert rest[0].strip() == ""
    assert rest != up


@pytest.mark.asyncio
async def test_dashboard_mascot_stays_on_idle_cycle() -> None:
    """Dashboard frog rests happy even on a critical selection (no panic art)."""
    app = BitCraftApp(
        store=Store(
            provider=DemoProvider(simulate_latency=False),
            is_demo=True,
            fast_boot=True,
            boot_log=["test"],
        )
    )
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.press("enter")
        for _ in range(200):
            if isinstance(app.screen, DashboardScreen) and app.store.boot_complete:
                break
            await pilot.pause(0.05)
        await pilot.pause(0.1)
        mascot = app.screen.query_one("#dashboard-mascot", Mascot)
        assert app.store.alert_page.items[0].severity == "critical"
        assert mascot.base_mood == "happy"
