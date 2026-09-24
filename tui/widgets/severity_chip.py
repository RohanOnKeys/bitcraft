"""Severity tier chip using existing alert-* styles only."""

from __future__ import annotations

from textual.widget import Widget

from tui.helpers.severity import SEVERITY_STYLE
from tui.providers.models import SeverityTier


class SeverityChip(Widget):
    """Colored severity label. Critical uses reversed styling via CSS."""

    DEFAULT_CSS = """
    SeverityChip {
        width: auto;
        height: 1;
        padding: 0 1;
    }
    SeverityChip.critical {
        background: #b3261e;
        color: #e6e6e6;
        text-style: bold;
    }
    """

    def __init__(self, tier: SeverityTier = "low", **kwargs) -> None:
        super().__init__(**kwargs)
        self.tier = tier

    def on_mount(self) -> None:
        style = SEVERITY_STYLE.get(self.tier, "alert-low")
        self.add_class(style)
        if self.tier == "critical":
            self.add_class("critical")

    def render(self) -> str:
        return self.tier.upper()
