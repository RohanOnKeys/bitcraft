"""Stacked severity distribution bar (critical/high/medium/low)."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.widget import Widget

from tui.widgets.chart import CRIMSON, MUTED, ORANGE, YELLOW


class StackedBar(Widget):
    """Single-line stacked bar using only palette colors via markup classes."""

    DEFAULT_CSS = """
    StackedBar {
        width: 100%;
        height: 1;
    }
    """

    def __init__(
        self,
        critical: int = 0,
        high: int = 0,
        medium: int = 0,
        low: int = 0,
        width: int = 40,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.critical = critical
        self.high = high
        self.medium = medium
        self.low = low
        self.bar_width = width

    def render(self) -> Text:
        total = self.critical + self.high + self.medium + self.low
        parts = [
            ("critical", self.critical, CRIMSON),
            ("high", self.high, ORANGE),
            ("medium", self.medium, YELLOW),
            ("low", self.low, "#5a5046"),
        ]
        legend_txt = Text(no_wrap=True, end="")
        for name, count, color in parts:
            legend_txt.append("  ■ ", Style(color=color))
            legend_txt.append(f"{name} ", Style(color=MUTED))
            legend_txt.append(f"{count:,}", Style(color=color, bold=True))
        width = max(10, self.size.width - legend_txt.cell_len - 1)
        bar = Text(no_wrap=True, end="")
        if total <= 0:
            bar.append("─" * width, Style(color=MUTED))
        else:
            remaining = width
            for i, (_, count, color) in enumerate(parts):
                n = remaining if i == len(parts) - 1 else min(remaining, round(count / total * width))
                # Keep tiny tiers visible.
                if count and n == 0 and remaining:
                    n = 1
                remaining -= n
                bar.append("█" * n, Style(color=color))
        bar.append(" ")
        bar.append_text(legend_txt)
        return bar
