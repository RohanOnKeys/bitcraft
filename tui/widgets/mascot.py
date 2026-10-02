"""Pixel frog mascot drawn with half-block characters.

Art lives in tui/assets/mascot/<mood>.png: one frog per mood on a shared
56x32 canvas (the art's native pixel grid, cut from the sprite sheet)
with a transparent background, bottom-aligned so switching
moods never makes the frog jump. Each PNG is downsampled to the requested
column width and drawn two pixels per cell with the upper-half block, which
keeps pixels square on a normal 1:2 terminal cell.

Moods by role:
  happy     resting default
  thinking  loading (boot stages)
  panic     a threat is in focus
  confused  boot failed
  the rest  idle cycle, flashed briefly while resting on happy

Liveliness: the frog hops up to four pixel rows (two cells) every couple
of seconds, and once on every mood change. The art keeps HOP_HEADROOM empty
pixel rows above it so hopping never shifts the surrounding layout.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Optional

from rich.color import Color
from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "mascot"

IDLE_MOODS: tuple[str, ...] = (
    "neutral",
    "sleepy",
    "confused",
    "shocked",
    "angry",
)
MOODS: tuple[str, ...] = ("happy", "thinking", "panic", *IDLE_MOODS)

# Idle cycle timing (seconds): rest on happy, then flash the next idle mood.
IDLE_GAP = 5.0
IDLE_HOLD = 2.5

# Bounce: pixel-row lift per animation frame, and seconds between hops.
# A full arc: quick lift, hang at the top, drop back down.
HOP_FRAMES: tuple[int, ...] = (1, 2, 3, 4, 4, 4, 3, 2, 1)
HOP_FRAME_S = 0.06
HOP_HEADROOM = max(HOP_FRAMES)
HOP_EVERY_S = 1.8
HOP_EVERY_BY_MOOD: dict[str, Optional[float]] = {
    "panic": 0.8,  # nervous
    "sleepy": 3.2,  # drowsy, hops less often
}

# Downsampling rules. The PNGs are stored at the art's native pixel grid
# (NATIVE_WIDTH columns), so NATIVE_WIDTH draws 1:1 and half of it 2:1.
NATIVE_WIDTH = 56
_MIN_COVER = 0.5  # share of a block that must be opaque to draw it
_FEATURE_SHARE = 0.5  # share of dark pixels that marks an eye/mouth block
_FEATURE_MAX_CHANNEL = 70  # brightest channel at or below this is "dark"

Pixel = Optional[tuple[int, int, int]]


@lru_cache(maxsize=64)
def mascot_pixels(mood: str, width: int) -> tuple[tuple[Pixel, ...], ...]:
    """Downsample a mood PNG to `width` columns; None marks transparency.

    Each block takes its most common colour rather than an average, so the
    art keeps its flat palette instead of smearing into mud. Row count is
    always even so rows pair up into half-block cells.
    """
    from PIL import Image  # local: keeps Pillow optional for non-UI imports

    with Image.open(ASSET_DIR / f"{mood}.png") as src:
        img = src.convert("RGBA")
    src_w, src_h = img.size
    height = max(2, round(src_h * width / src_w / 2) * 2)
    data = img.load()

    rows: list[tuple[Pixel, ...]] = []
    for y in range(height):
        y0, y1 = y * src_h // height, max(y * src_h // height + 1, (y + 1) * src_h // height)
        row: list[Pixel] = []
        for x in range(width):
            x0, x1 = x * src_w // width, max(x * src_w // width + 1, (x + 1) * src_w // width)
            total = (y1 - y0) * (x1 - x0)
            dark: Counter[tuple[int, int, int]] = Counter()
            lit: Counter[tuple[int, int, int]] = Counter()
            for sy in range(y0, y1):
                for sx in range(x0, x1):
                    r, g, b, a = data[sx, sy]
                    if a < 128:
                        continue
                    if max(r, g, b) <= _FEATURE_MAX_CHANNEL:
                        dark[(r, g, b)] += 1
                    else:
                        lit[(r, g, b)] += 1
            n_dark, n_lit = sum(dark.values()), sum(lit.values())
            opaque = n_dark + n_lit
            if opaque == 0 or opaque < _MIN_COVER * total:
                row.append(None)
            elif n_dark >= _FEATURE_SHARE * opaque:
                row.append(dark.most_common(1)[0][0])
            else:
                row.append(lit.most_common(1)[0][0])
        rows.append(tuple(row))
    return tuple(rows)


@lru_cache(maxsize=256)
def render_mascot(mood: str, width: int, lift: int = 0) -> Text:
    """Rich Text for one mood at `width` columns, raised `lift` pixel rows.

    Always HOP_HEADROOM pixel rows taller than the art, so every lift
    renders at the same height.
    """
    if not 0 <= lift <= HOP_HEADROOM:
        raise ValueError(f"lift must be within 0..{HOP_HEADROOM}")
    blank: tuple[Pixel, ...] = (None,) * width
    pad = HOP_HEADROOM + HOP_HEADROOM % 2  # keep pixel rows even
    pixels = (
        (blank,) * (pad - lift) + mascot_pixels(mood, width) + (blank,) * lift
    )
    text = Text(no_wrap=True, end="")
    for i in range(0, len(pixels), 2):
        for top, bottom in zip(pixels[i], pixels[i + 1]):
            if top is None and bottom is None:
                text.append(" ")
            elif bottom is None:
                text.append("▀", Style(color=Color.from_rgb(*top)))
            elif top is None:
                text.append("▄", Style(color=Color.from_rgb(*bottom)))
            else:
                text.append(
                    "▀",
                    Style(color=Color.from_rgb(*top), bgcolor=Color.from_rgb(*bottom)),
                )
        if i + 2 < len(pixels):
            text.append("\n")
    return text


class Mascot(Static):
    """The BitCraft frog. Set a resting mood with `set_base`.

    With `bounce=True` (the default) the frog hops now and then; see the
    module docstring. With `idle=True`, while resting on happy the frog periodically flashes
    the next idle mood for IDLE_HOLD seconds. Other resting moods (thinking,
    panic, confused) hold still so the signal is not diluted.
    """

    DEFAULT_CSS = """
    Mascot {
        width: auto;
        height: auto;
    }
    """

    mood: reactive[str] = reactive("happy")
    lift: reactive[int] = reactive(0)

    def __init__(
        self,
        mood: str = "happy",
        *,
        art_width: int = 26,
        idle: bool = False,
        bounce: bool = True,
        **kwargs,
    ) -> None:
        super().__init__("", **kwargs)
        self.art_width = art_width
        self.base_mood = mood
        self._idle = idle
        self._idle_index = 0
        self._idle_timer: Optional[Timer] = None
        self._bounce = bounce
        self._hop_frame: Optional[int] = None
        self._ticks_since_hop = 0
        self.set_reactive(Mascot.mood, mood)

    def on_mount(self) -> None:
        self._show()
        if self._idle:
            self._idle_timer = self.set_timer(IDLE_GAP, self._idle_flash)
        if self._bounce:
            self.set_interval(HOP_FRAME_S, self._bounce_tick)

    def watch_mood(self, _mood: str) -> None:
        self._show()
        self._hop()

    def watch_lift(self, _lift: int) -> None:
        self._show()

    def _show(self) -> None:
        try:
            self.update(render_mascot(self.mood, self.art_width, self.lift))
        except (ImportError, OSError):
            # Pillow or art missing: the frog is decoration, never a blocker.
            self.display = False

    def _hop(self) -> None:
        """Start a hop unless one is running or this mood stays still."""
        if not self._bounce or self._hop_frame is not None:
            return
        if HOP_EVERY_BY_MOOD.get(self.mood, HOP_EVERY_S) is None:
            return
        self._hop_frame = 0
        self.lift = HOP_FRAMES[0]

    def _bounce_tick(self) -> None:
        if self._hop_frame is not None:
            self._hop_frame += 1
            if self._hop_frame < len(HOP_FRAMES):
                self.lift = HOP_FRAMES[self._hop_frame]
                return
            self._hop_frame = None
            self._ticks_since_hop = 0
            self.lift = 0
            return
        every = HOP_EVERY_BY_MOOD.get(self.mood, HOP_EVERY_S)
        if every is None:
            return
        self._ticks_since_hop += 1
        if self._ticks_since_hop * HOP_FRAME_S >= every:
            self._hop()

    def hop(self) -> None:
        """Jump now (e.g. to react to a selection change)."""
        self._hop()

    def set_art_width(self, width: int) -> None:
        """Redraw at a new column width (e.g. to fit a resized screen)."""
        if width != self.art_width:
            self.art_width = width
            self._show()

    def set_base(self, mood: str) -> None:
        """Change the resting mood and show it now (ends any idle flash)."""
        self.base_mood = mood
        self.mood = mood

    def _idle_flash(self) -> None:
        if self.base_mood == "happy" and self.mood == "happy":
            self.mood = IDLE_MOODS[self._idle_index % len(IDLE_MOODS)]
            self._idle_index += 1
            self._idle_timer = self.set_timer(IDLE_HOLD, self._idle_return)
        else:
            self._idle_timer = self.set_timer(IDLE_GAP, self._idle_flash)

    def _idle_return(self) -> None:
        # A set_base during the flash already moved us off the idle mood.
        if self.mood in IDLE_MOODS:
            self.mood = self.base_mood
        self._idle_timer = self.set_timer(IDLE_GAP, self._idle_flash)
