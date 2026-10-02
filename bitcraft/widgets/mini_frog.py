"""A small, crisp pixel frog for the gaps between panels.

The full mascot (bitcraft/widgets/mascot.py) only looks right at its native 56
columns; shrinking it smears the face. This one is drawn at its own size
(18x12 pixels -> 18 columns x 6 rows, plus hop headroom) in the same
palette, hops on its own rhythm and blinks now and then.
"""

from __future__ import annotations

import random

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

PALETTE = {
    "G": "#c6a02e",  # body
    "S": "#b68d21",  # shade
    "D": "#8a610e",  # deep shade / feet
    "K": "#2b200c",  # eyes and mouth
    "L": "#e2c25a",  # highlight
}

OPEN = (
    "..LL..........LL..",
    ".LGGL........LGGL.",
    ".GKKG........GKKG.",
    ".GGGGGGGGGGGGGGGG.",
    "GGGGGGGGGGGGGGGGGG",
    "GLGGGGGGGGGGGGGGLG",
    "GGGKGGGGGGGGGGKGGG",
    "SGGGKKKKKKKKKKGGGS",
    "SGGGGGGGGGGGGGGGGS",
    ".SSGGGGGGGGGGGGSS.",
    ".DD.SGGGGGGGGS.DD.",
    "DDD..DD....DD..DDD",
)
# Blink: eyes become a line.
BLINK = OPEN[:2] + (".GGGG........GGGG.", ".GKKGGGGGGGGGGKKG.") + OPEN[4:]

HEADROOM = 2  # pixel rows reserved above the frog for hopping
HOP = (1, 2, 2, 1)
FPS = 10


def render_mini(lift: int = 0, blink: bool = False) -> Text:
    """Rich Text for the frog raised `lift` pixel rows (0..HEADROOM)."""
    art = BLINK if blink else OPEN
    width = len(art[0])
    rows = ["." * width] * (HEADROOM - lift) + list(art) + ["." * width] * lift
    text = Text(no_wrap=True, end="")
    for i in range(0, len(rows), 2):
        top, bottom = rows[i], rows[i + 1]
        for t, b in zip(top, bottom):
            tc, bc = PALETTE.get(t), PALETTE.get(b)
            if tc is None and bc is None:
                text.append(" ")
            elif bc is None:
                text.append("▀", Style(color=tc))
            elif tc is None:
                text.append("▄", Style(color=bc))
            else:
                text.append("▀", Style(color=tc, bgcolor=bc))
        if i + 2 < len(rows):
            text.append("\n")
    return text


class MiniFrog(Static):
    """Small hopping, blinking frog. Each instance keeps its own rhythm."""

    DEFAULT_CSS = """
    MiniFrog {
        width: 18;
        height: 7;
    }
    """

    def __init__(self, *, seed: int | None = None, **kwargs) -> None:
        super().__init__(render_mini(), **kwargs)
        self._rng = random.Random(seed)
        self._tick = 0
        self._hop_at = self._rng.randint(8, 30)
        self._hop_frame: int | None = None
        self._blink_left = 0

    def on_mount(self) -> None:
        self.set_interval(1 / FPS, self._step)

    def _step(self) -> None:
        self._tick += 1
        lift = 0
        if self._hop_frame is not None:
            lift = HOP[self._hop_frame]
            self._hop_frame += 1
            if self._hop_frame >= len(HOP):
                self._hop_frame = None
                self._hop_at = self._tick + self._rng.randint(12, 35)
        elif self._tick >= self._hop_at:
            self._hop_frame = 0
        if self._blink_left:
            self._blink_left -= 1
        elif self._rng.random() < 0.02:
            self._blink_left = 2
        self.update(render_mini(lift, blink=self._blink_left > 0))
