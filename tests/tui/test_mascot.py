"""Tests for the frog mascot art, renderer, and mood wiring."""

import pytest

from bitcraft.app import BitCraftApp
from bitcraft.providers.demo_provider import DemoProvider
from bitcraft.screens.dashboard import DashboardScreen
from bitcraft.store import Store
from bitcraft.widgets.mascot import (
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
async def test_frogs_only_on_loading_screens() -> None:
    """Data pages stay frog-free; the splash keeps its frog."""
    from bitcraft.screens.splash import SplashScreen
    from bitcraft.widgets.mini_frog import MiniFrog

    app = BitCraftApp(
        store=Store(
            provider=DemoProvider(simulate_latency=False),
            is_demo=True,
            fast_boot=True,
            boot_log=["test"],
        )
    )
    async with app.run_test(size=(180, 50)) as pilot:
        assert isinstance(app.screen, SplashScreen)
        assert app.screen.query(Mascot) and app.screen.query(MiniFrog)
        await pilot.press("enter")
        for _ in range(200):
            if isinstance(app.screen, DashboardScreen) and app.store.boot_complete:
                break
            await pilot.pause(0.05)
        for key in ("d", "t", "g", "w"):
            await pilot.press(key)
            await pilot.pause(0.2)
            assert not app.screen.query(Mascot), key
            assert not app.screen.query(MiniFrog), key
