"""Inline composite score bar widget."""

from __future__ import annotations

from textual.widget import Widget

from tui.helpers.format import score_bar


class ScoreBar(Widget):
    """Renders a filled score bar such as #######---."""

    DEFAULT_CSS = """
    ScoreBar {
        width: auto;
        height: 1;
        color: #d4af37;
    }
    """

    def __init__(self, score: float = 0.0, width: int = 10, **kwargs) -> None:
        super().__init__(**kwargs)
        self.score = score
        self.bar_width = width

    def render(self) -> str:
        return score_bar(self.score, self.bar_width)
