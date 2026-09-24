"""Stacked severity distribution bar (critical/high/medium/low)."""

from __future__ import annotations

from textual.widget import Widget


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

    def render(self) -> str:
        total = self.critical + self.high + self.medium + self.low
        if total <= 0:
            return "-" * self.bar_width
        parts = [
            (self.critical, "#b3261e"),
            (self.high, "#b3261e"),
            (self.medium, "#d4af37"),
            (self.low, "#7a7a7a"),
        ]
        chars: list[str] = []
        remaining = self.bar_width
        for i, (count, color) in enumerate(parts):
            if i == len(parts) - 1:
                n = remaining
            else:
                n = int(round(count / total * self.bar_width))
                n = min(n, remaining)
                remaining -= n
            if n > 0:
                chars.append(f"[{color}]{'#' * n}[/]")
        return "".join(chars) if chars else "-" * self.bar_width
