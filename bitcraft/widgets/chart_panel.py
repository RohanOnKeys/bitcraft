"""Chart panel widgets that size themselves to their container.

Each panel renders the series the screen hands it (from GET /stats/charts,
/threats/overview and /communities) and redraws on resize; a few carry a
gentle animation so the screen feels live. With no data a panel says so
instead of drawing anything.
"""

from __future__ import annotations

import math
from typing import Sequence

from rich.style import Style
from rich.text import Text
from textual.widget import Widget

from bitcraft.widgets.chart import (
    CHROME,
    CRIMSON,
    DIM,
    HEAT_RAMP,
    MUTED,
    ORANGE,
    PINK,
    RISK_RAMP,
    SALMON,
    TEXT,
    YELLOW,
    Canvas,
    column_chart,
    dim,
    donut,
    gradient_bar,
    heatmap,
    hbar,
    legend,
    ramp,
    sparkline,
)


def no_data(message: str = "no data") -> Text:
    """Muted placeholder line for a panel whose series is empty."""
    return Text(message, style=Style(color=MUTED, italic=True))


class _Animated(Widget):
    """Widget that redraws on a timer and exposes a frame counter."""

    FPS = 8

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.frame = 0

    def on_mount(self) -> None:
        self.set_interval(1 / self.FPS, self._tick)

    def _tick(self) -> None:
        self.frame += 1
        self.refresh()


class TimestepChart(_Animated):
    """Alert volume per Elliptic timestep: columns plus a sweeping cursor."""

    def __init__(self, series: Sequence[float] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.series = list(series or [])

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 12 or h < 4:
            return Text("")
        if not self.series:
            return no_data()
        axis_w = 5
        plot_w = w - axis_w
        chart_h = h - 2
        # Resample the series to the plot width.
        n = len(self.series)
        cols = [self.series[min(n - 1, int(i * n / plot_w))] for i in range(plot_w)]
        sweep = (self.frame // 2) % plot_w
        body = column_chart(cols, chart_h, highlight=sweep)
        peak = max(self.series)
        out = Text(no_wrap=True, end="")
        for r, line in enumerate(body.split("\n")):
            label = ""
            if r == 0:
                label = f"{peak:>4.0f}"
            elif r == chart_h // 2:
                label = f"{peak / 2:>4.0f}"
            elif r == chart_h - 1:
                label = f"{0:>4}"
            out.append(f"{label:>4}", Style(color=MUTED))
            out.append("│", Style(color=DIM))
            out.append_text(line)
            out.append("\n")
        out.append(" " * 4 + "└" + "─" * plot_w + "\n", Style(color=DIM))
        ts = min(n, int(sweep * n / plot_w) + 1)
        tick = Text(no_wrap=True, end="")
        tick.append(" " * 5 + "t1", Style(color=MUTED))
        mid = f"timestep {ts:>2} · {self.series[ts - 1]:.0f} alerts"
        pad = max(1, (plot_w - len(mid)) // 2 - 2)
        tick.append(" " * pad)
        tick.append(mid, Style(color=YELLOW, bold=True))
        tail = "t49"
        rest = w - tick.cell_len - len(tail)
        tick.append(" " * max(1, rest))
        tick.append(tail, Style(color=MUTED))
        out.append_text(tick)
        return out


# Legend column beside a donut: "■ " + 10-char name + 4-char share + gap.
LEGEND_W = 18


class DonutChart(_Animated):
    """Ring chart with legend and share percentages."""

    FPS = 6

    def __init__(
        self,
        segments: Sequence[tuple[str, float, str]],
        label: str = "",
        sublabel: str = "",
        spin: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.segments = list(segments)
        self.label = label
        self.sublabel = sublabel
        self.spin = spin

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 10 or h < 4:
            return Text("")
        if not self.segments:
            return no_data()
        legend_rows = len(self.segments)
        side = w >= 34
        ring_rows = h if side else max(4, h - legend_rows)
        ring_cols = min(ring_rows * 2, w if not side else w - LEGEND_W)
        ring_rows = min(ring_rows, ring_cols // 2)
        ring = donut(
            [(v, c) for _, v, c in self.segments], ring_cols, ring_rows,
            label=self.label, sublabel=self.sublabel,
            spin=self.frame * 0.02 if self.spin else 0.0,
        ).split("\n")
        total = sum(v for _, v, _ in self.segments) or 1
        leg = []
        for name, v, color in self.segments:
            t = Text(no_wrap=True, end="")
            t.append("■ ", Style(color=color))
            t.append(f"{name:<10}", Style(color=TEXT))
            t.append(f"{v / total:>4.0%}", Style(color=color, bold=True))
            leg.append(t)
        out = Text(no_wrap=True, end="")
        if side:
            top = max(0, (len(ring) - len(leg)) // 2)
            for i in range(max(len(ring), top + len(leg))):
                line = ring[i] if i < len(ring) else Text(" " * ring_cols)
                out.append_text(line)
                out.append(" " * (ring_cols - line.cell_len) + "  ")
                j = i - top
                if 0 <= j < len(leg):
                    out.append_text(leg[j])
                out.append("\n")
        else:
            pad = (w - ring_cols) // 2
            for line in ring:
                out.append(" " * pad)
                out.append_text(line)
                out.append("\n")
            for t in leg:
                out.append_text(t)
                out.append("\n")
        out.rstrip()
        return out


class CommunityBars(_Animated):
    """Top communities by illicit ratio: gradient bars that grow in."""

    FPS = 20

    def __init__(self, rows: Sequence[tuple[str, float, int]] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.rows = list(rows or [])

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 16:
            return Text("")
        if not self.rows:
            return no_data()
        grow = min(1.0, self.frame / 25)
        bar_w = max(4, w - 17)
        out = Text(no_wrap=True, end="")
        for i, (label, ratio, size) in enumerate(self.rows[:h]):
            out.append(f"{label:<4}", Style(color=ramp(ratio, RISK_RAMP), bold=True))
            out.append_text(gradient_bar(ratio * grow, bar_w))
            out.append(f" {ratio:.2f}", Style(color=TEXT))
            out.append(f" {size:>5}", Style(color=MUTED))
            if i < min(h, len(self.rows)) - 1:
                out.append("\n")
        return out

    def _tick(self) -> None:
        if self.frame < 30:
            super()._tick()


class HeatmapChart(Widget):
    """Rows x timesteps heatmap: suspicious transactions per source country.

    Two rows share one text line (upper half block), so each line is
    labelled with both row names.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.rows: list[str] = []
        self.matrix: list[list[float]] = []

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 20 or h < 4:
            return Text("")
        if not self.matrix:
            return no_data("no metadata loaded")
        label_w = 6
        cols = len(self.matrix[0])
        cell_w = max(1, (w - label_w) // cols)
        n_rows = min(len(self.matrix), (h - 2) * 2)
        body = heatmap(self.matrix[:n_rows], cell_w=cell_w).split("\n")
        names = self.rows[:n_rows]
        out = Text(no_wrap=True, end="")
        for i, line in enumerate(body):
            pair = " ".join(names[2 * i:2 * i + 2])
            out.append(f"{pair:<{label_w}}", Style(color=MUTED))
            out.append_text(line)
            out.append("\n")
        plot_w = cols * cell_w
        ticks = Text(" " * label_w, no_wrap=True, end="")
        ticks.append("t1", Style(color=MUTED))
        ticks.append(" " * max(1, plot_w - 5))
        ticks.append("t49", Style(color=MUTED))
        scale = Text(no_wrap=True, end="")
        scale.append(" low ", Style(color=MUTED))
        for i in range(5):
            scale.append("█", Style(color=ramp(i / 4, HEAT_RAMP)))
        scale.append(" hi", Style(color=MUTED))
        out.append_text(ticks)
        if ticks.cell_len + scale.cell_len <= w:
            out.append_text(scale)
        return out


class FlowChart(Widget):
    """BTC volume per timestep: all transactions vs alerted ones.

    Drawn on one shared scale so the alerted share reads honestly; the
    all-volume series is filled, the alerted series is a line on top.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.total: list[float] = []
        self.alerted: list[float] = []

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 12 or h < 4:
            return Text("")
        if not self.total:
            return no_data("no metadata loaded")
        canvas = Canvas(w, h - 1)
        peak = max(max(self.total), max(self.alerted or [0])) * 1.1 or 1
        for values, color in ((self.total, SALMON), (self.alerted, YELLOW)):
            n = len(values)
            if not n:
                continue
            prev = None
            for x in range(canvas.w):
                f = x / max(1, canvas.w - 1) * (n - 1)
                i = int(f)
                v = values[i] + (values[min(n - 1, i + 1)] - values[i]) * (f - i)
                y = canvas.h - 1 - v / peak * (canvas.h - 1)
                if color == SALMON:
                    for yy in range(int(y) + 2, canvas.h, 2):
                        canvas.dot(x, yy, dim(SALMON, 0.55), prio=0)
                if prev is not None:
                    canvas.line(x - 1, prev, x, y, color, prio=3)
                prev = y
        out = canvas.to_text()
        out.append("\n")
        share = sum(self.alerted) / (sum(self.total) or 1)
        out.append_text(legend([
            (f"all BTC, peak {max(self.total):,.0f}", SALMON),
            (f"alerted BTC, {share:.1%} of volume", YELLOW),
        ]))
        return out


class DegreeChart(Widget):
    """Transaction-graph degree histogram on a log scale (heavy tail)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.buckets: list[str] = []
        self.counts: list[int] = []

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 10 or h < 3:
            return Text("")
        if not self.counts:
            return no_data()
        n = min(len(self.counts), w // 2)
        heights = [math.log10(1 + c) for c in self.counts[:n]]
        body = column_chart(heights, h - 1, ramp_stops=(YELLOW, CHROME, ORANGE, SALMON, PINK), gap=True)
        body.append("\n")
        first, last = self.buckets[0], self.buckets[n - 1]
        span = n * 2
        body.append(first + " " * max(1, span - len(first) - len(last)) + last, Style(color=MUTED))
        peak = f"max {max(self.counts):,}"
        if span + len(peak) + 2 <= w:
            body.append("  " + peak, Style(color=MUTED))
        return body


class StatTiles(Widget):
    """Stacked stat rows, each with a value and a mini sparkline."""

    def __init__(self, stats: Sequence[tuple[str, str, Sequence[float], str]], **kwargs) -> None:
        super().__init__(**kwargs)
        self.stats = list(stats)

    def render(self) -> Text:
        w = self.size.width
        out = Text(no_wrap=True, end="")
        for i, (name, value, series, color) in enumerate(self.stats):
            out.append(f"{name:<11}", Style(color=MUTED))
            out.append(f"{value:>8} ", Style(color=color, bold=True))
            spark_w = max(0, w - 21)
            if spark_w and series:
                n = len(series)
                pts = [series[min(n - 1, int(j * n / spark_w))] for j in range(spark_w)]
                out.append_text(sparkline(pts))
            if i < len(self.stats) - 1:
                out.append("\n")
        return out


def score_gauge(score: float, width: int = 30) -> Text:
    """Composite score as a gradient gauge with a needle marker."""
    out = Text(no_wrap=True, end="")
    for i in range(width):
        t = i / max(1, width - 1)
        color = ramp(t, RISK_RAMP)
        out.append("━" if t > score else "█", Style(color=color if t <= score else dim(color, 0.7)))
    out.append(f" {score:.3f}", Style(color=ramp(score, RISK_RAMP), bold=True))
    return out


def driver_bars(parts: Sequence[tuple[str, float, str]], width: int = 24) -> Text:
    """Labelled horizontal bars, one per driver."""
    peak = max((v for _, v, _ in parts), default=1) or 1
    out = Text(no_wrap=True, end="")
    for i, (name, v, color) in enumerate(parts):
        out.append(f"{name:<10}", Style(color=color, bold=True))
        out.append_text(hbar(v / peak, width, color))
        out.append(f" {v:.3f}", Style(color=TEXT))
        if i < len(parts) - 1:
            out.append("\n")
    return out


def severity_colour(tier: str) -> str:
    """Palette colour for a severity tier."""
    return {"critical": CRIMSON, "high": ORANGE, "medium": YELLOW, "low": MUTED}.get(tier, MUTED)


DRIVER_COLOURS = {"MODEL": YELLOW, "ANOMALY": SALMON, "COMMUNITY": CHROME, "NETWORK": PINK}
