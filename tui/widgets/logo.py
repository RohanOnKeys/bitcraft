"""ASCII BitCraft logo.

Classic block wordmark, pure ASCII so it renders the same on every
terminal. Gold accent is applied by the parent screen via theme.tcss.
"""

from textual.widgets import Static

# FIGlet "standard" style, hand-trimmed for a compact TUI header.
# Kept as a constant so splash and dashboard share one logo.
BITCRAFT_LOGO = r"""
 ____  _ _    ____            __ _
| __ )(_) |_ / ___|_ __ __ _ / _| |_
|  _ \| | __| |   | '__/ _` | |_| __|
| |_) | | |_| |___| | | (_| |  _| |_
|____/|_|\__|\____|_|  \__,_|_|  \__|
""".strip(
    "\n"
)

BITCRAFT_TAGLINE = "Bitcoin Transaction Intelligence"


class Logo(Static):
    """Centered ASCII BitCraft wordmark."""

    DEFAULT_CSS = """
    Logo {
        width: 100%;
        height: auto;
        content-align: center middle;
        color: #d4af37;
        text-style: bold;
    }
    """

    def __init__(self, *, show_tagline: bool = False, **kwargs) -> None:
        text = BITCRAFT_LOGO
        if show_tagline:
            text = f"{BITCRAFT_LOGO}\n\n{BITCRAFT_TAGLINE}"
        super().__init__(text, **kwargs)
