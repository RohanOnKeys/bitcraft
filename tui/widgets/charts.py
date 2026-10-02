"""Terminal chart primitives: braille canvas, columns, bars, donut, heatmap.

Everything renders to Rich Text so any Static or Widget can show it. The
chart palette is warm on purpose (yellow, chrome yellow, orange, salmon,
light pink) so charts sit with the gold UI accent instead of fighting it.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from rich.style import Style
from rich.text import Text

YELLOW = "#ffd84d"
CHROME = "#ffa700"
ORANGE = "#ff8c42"
SALMON = "#fa8072"
PINK = "#ffb6c1"
GOLD = "#d4af37"
CRIMSON = "#e0524a"
DIM = "#5a5046"
MUTED = "#8a8078"
TEXT = "#e6e6e6"

SERIES: tuple[str, ...] = (SALMON, CHROME, PINK, ORANGE, YELLOW)
# Low -> high intensity ramps.
HEAT_RAMP: tuple[str, ...] = ("#1a120c", "#4a2c1c", SALMON, ORANGE, CHROME, YELLOW)
RISK_RAMP: tuple[str, ...] = (PINK, SALMON, ORANGE, CHROME, YELLOW)

_EIGHTHS = " ▁▂▃▄▅▆▇█"
_H_EIGHTHS = " ▏▎▍▌▋▊▉█"
_BRAILLE_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    """Blend two hex colours, t=0 -> a, t=1 -> b."""
    t = max(0.0, min(1.0, t))
    ra, ga, ba = _hex(a)
    rb, gb, bb = _hex(b)
    return "#{:02x}{:02x}{:02x}".format(
        round(ra + (rb - ra) * t), round(ga + (gb - ga) * t), round(ba + (bb - ba) * t)
    )


def ramp(t: float, stops: Sequence[str] = RISK_RAMP) -> str:
    """Colour at position t (0..1) along a multi-stop ramp."""
    t = max(0.0, min(1.0, t))
    seg = t * (len(stops) - 1)
    i = min(len(stops) - 2, int(seg))
    return mix(stops[i], stops[i + 1], seg - i)


def dim(c: str, amount: float = 0.55) -> str:
    """Darken a colour toward black."""
    return mix(c, "#000000", amount)


# --- Braille canvas ---------------------------------------------------------


class Canvas:
    """Braille dot canvas (2x4 dots per cell) with a text overlay layer.

    Braille dots on a 1:2 cell are square, so circles stay round. Each cell
    holds one colour; the highest-priority write wins.
    """

    def __init__(self, cols: int, rows: int) -> None:
        self.cols = max(1, cols)
        self.rows = max(1, rows)
        self.w = self.cols * 2
        self.h = self.rows * 4
        self._bits = [[0] * self.cols for _ in range(self.rows)]
        self._color: list[list[Optional[str]]] = [[None] * self.cols for _ in range(self.rows)]
        self._prio = [[-1] * self.cols for _ in range(self.rows)]
        self._over: dict[tuple[int, int], tuple[str, Style]] = {}

    def dot(self, x: float, y: float, color: str, prio: int = 0) -> None:
        xi, yi = int(round(x)), int(round(y))
        if not (0 <= xi < self.w and 0 <= yi < self.h):
            return
        cx, cy = xi >> 1, yi >> 2
        self._bits[cy][cx] |= _BRAILLE_BITS[yi & 3][xi & 1]
        if prio >= self._prio[cy][cx]:
            self._prio[cy][cx] = prio
            self._color[cy][cx] = color

    def line(
        self, x0: float, y0: float, x1: float, y1: float, color: str,
        prio: int = 0, dash: int = 0,
    ) -> None:
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(steps + 1):
            if dash and (i // dash) % 2:
                continue
            t = i / steps
            self.dot(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, color, prio)

    def circle(self, x: float, y: float, r: float, color: str, prio: int = 0) -> None:
        n = max(12, int(r * 7))
        for i in range(n):
            a = 2 * math.pi * i / n
            self.dot(x + r * math.cos(a), y + r * math.sin(a), color, prio)

    def put(self, col: int, row: int, s: str, style: Style | str) -> None:
        """Overlay text at a cell position (clipped to the canvas)."""
        st = Style.parse(style) if isinstance(style, str) else style
        for i, ch in enumerate(s):
            c = col + i
            if 0 <= c < self.cols and 0 <= row < self.rows:
                self._over[(c, row)] = (ch, st)

    def to_text(self) -> Text:
        text = Text(no_wrap=True, end="")
        for r in range(self.rows):
            for c in range(self.cols):
                over = self._over.get((c, r))
                if over is not None:
                    text.append(over[0], over[1])
                    continue
                bits = self._bits[r][c]
                if bits:
                    text.append(chr(0x2800 + bits), Style(color=self._color[r][c]))
                else:
                    text.append(" ")
            if r < self.rows - 1:
                text.append("\n")
        return text


# --- Charts ----------------------------------------------------------------


def column_chart(
    values: Sequence[float], height: int, *, ramp_stops: Sequence[str] = RISK_RAMP,
    gap: bool = False, highlight: Optional[int] = None,
) -> Text:
    """Vertical columns with eighth-block tops, coloured by height."""
    peak = max(values) if values else 1
    peak = peak or 1
    text = Text(no_wrap=True, end="")
    levels = [v / peak * height * 8 for v in values]
    for row in range(height):
        floor = (height - 1 - row) * 8
        for i, lv in enumerate(levels):
            part = int(max(0, min(8, lv - floor)))
            color = ramp(values[i] / peak, ramp_stops)
            if highlight is not None and i == highlight:
                color = TEXT
            text.append(_EIGHTHS[part] if part else " ", Style(color=color))
            if gap:
                text.append(" ")
        if row < height - 1:
            text.append("\n")
    return text


def hbar(value: float, width: int, color: str, track: str = "#1c1814") -> Text:
    """One horizontal bar with eighth-block precision on a dim track."""
    value = max(0.0, min(1.0, value))
    full_eighths = int(round(value * width * 8))
    full, part = divmod(full_eighths, 8)
    text = Text(no_wrap=True, end="")
    text.append("█" * full, Style(color=color))
    if full < width:
        if part:
            text.append(_H_EIGHTHS[part], Style(color=color, bgcolor=track))
            full += 1
        text.append(" " * (width - full), Style(bgcolor=track))
    return text


def gradient_bar(value: float, width: int, stops: Sequence[str] = RISK_RAMP) -> Text:
    """Horizontal bar whose fill runs along the colour ramp."""
    value = max(0.0, min(1.0, value))
    filled = int(round(value * width))
    text = Text(no_wrap=True, end="")
    for i in range(width):
        if i < filled:
            text.append("█", Style(color=ramp(i / max(1, width - 1), stops)))
        else:
            text.append("·", Style(color="#2a2420"))
    return text


def sparkline(values: Sequence[float], stops: Sequence[str] = RISK_RAMP) -> Text:
    """One-row sparkline coloured by value."""
    peak = max(values) if values else 1
    peak = peak or 1
    text = Text(no_wrap=True, end="")
    for v in values:
        idx = int(round(v / peak * 7))
        text.append("▁▂▃▄▅▆▇█"[idx], Style(color=ramp(v / peak, stops)))
    return text


def heatmap(matrix: Sequence[Sequence[float]], cell_w: int = 2) -> Text:
    """Two matrix rows per text row using the upper half block."""
    flat = [v for row in matrix for v in row]
    peak = max(flat) if flat else 1
    peak = peak or 1
    rows = list(matrix)
    if len(rows) % 2:
        rows.append([0.0] * len(rows[0]))
    text = Text(no_wrap=True, end="")
    for i in range(0, len(rows), 2):
        for top, bot in zip(rows[i], rows[i + 1]):
            st = Style(color=ramp(top / peak, HEAT_RAMP), bgcolor=ramp(bot / peak, HEAT_RAMP))
            text.append("▀" * cell_w, st)
        if i + 2 < len(rows):
            text.append("\n")
    return text


def donut(
    segments: Sequence[tuple[float, str]], cols: int, rows: int,
    *, label: str = "", sublabel: str = "", spin: float = 0.0,
) -> Text:
    """Solid ring split into coloured arcs, drawn with half blocks.

    Two square pixels per cell (upper-half block, fg = top, bg = bottom), so
    the ring is solid and round. Labels sit in the hole.
    """
    total = sum(v for v, _ in segments) or 1
    bounds: list[tuple[float, str]] = []
    acc = 0.0
    for v, color in segments:
        acc += v / total
        bounds.append((acc, color))
    w, h = cols, rows * 2
    cx, cy = w / 2 - 0.5, h / 2 - 0.5
    r_out = min(w, h) / 2 - 0.2
    r_in = r_out * 0.58

    def pixel(x: int, y: int) -> Optional[str]:
        dx, dy = x - cx, y - cy
        r = math.hypot(dx, dy)
        if not (r_in <= r <= r_out):
            return None
        frac = ((math.atan2(dy, dx) + math.pi / 2 + spin) / (2 * math.pi)) % 1.0
        for edge, color in bounds:
            if frac <= edge:
                return color
        return bounds[-1][1]

    mid = rows // 2
    overlay: dict[int, tuple[str, Style]] = {}
    if label:
        overlay[mid - (1 if sublabel else 0)] = (label, Style(color=YELLOW, bold=True))
    if sublabel:
        overlay[mid] = (sublabel, Style(color=MUTED))
    text = Text(no_wrap=True, end="")
    for row in range(rows):
        line = Text(no_wrap=True, end="")
        for x in range(w):
            top, bot = pixel(x, row * 2), pixel(x, row * 2 + 1)
            if top is None and bot is None:
                line.append(" ")
            elif bot is None:
                line.append("▀", Style(color=top))
            elif top is None:
                line.append("▄", Style(color=bot))
            else:
                line.append("▀", Style(color=top, bgcolor=bot))
        if row in overlay:
            s_, st = overlay[row]
            start = max(0, (w - len(s_)) // 2)
            plain = line.plain
            # Only write over blank hole cells.
            if plain[start:start + len(s_)].strip() == "":
                head = line[:start]
                tail = line[start + len(s_):]
                line = Text(no_wrap=True, end="")
                line.append_text(head)
                line.append(s_, st)
                line.append_text(tail)
        text.append_text(line)
        if row < rows - 1:
            text.append("\n")
    return text


def legend(items: Iterable[tuple[str, str]], sep: str = "  ") -> Text:
    """Inline ● label legend."""
    text = Text(no_wrap=True, end="")
    for i, (name, color) in enumerate(items):
        if i:
            text.append(sep)
        text.append("● ", Style(color=color))
        text.append(name, Style(color=MUTED))
    return text
