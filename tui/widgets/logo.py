"""Solid block BitCraft logo.

"ANSI Shadow" style wordmark: full blocks for the letter faces, box-drawing
strokes for the drop shadow. Faces take a warm top-to-bottom gradient
(yellow -> chrome -> orange -> salmon); shadows stay a dim bronze so the
letters read as solid, lit shapes.
"""

from rich.style import Style
from rich.text import Text
from textual.widgets import Static

_GLYPHS: dict[str, tuple[str, ...]] = {
    "B": (
        "██████╗ ",
        "██╔══██╗",
        "██████╔╝",
        "██╔══██╗",
        "██████╔╝",
        "╚═════╝ ",
    ),
    "I": (
        "██╗",
        "██║",
        "██║",
        "██║",
        "██║",
        "╚═╝",
    ),
    "T": (
        "████████╗",
        "╚══██╔══╝",
        "   ██║   ",
        "   ██║   ",
        "   ██║   ",
        "   ╚═╝   ",
    ),
    "C": (
        " ██████╗",
        "██╔════╝",
        "██║     ",
        "██║     ",
        "╚██████╗",
        " ╚═════╝",
    ),
    "R": (
        "██████╗ ",
        "██╔══██╗",
        "██████╔╝",
        "██╔══██╗",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ),
    "A": (
        " █████╗ ",
        "██╔══██╗",
        "███████║",
        "██╔══██║",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ),
    "F": (
        "███████╗",
        "██╔════╝",
        "█████╗  ",
        "██╔══╝  ",
        "██║     ",
        "╚═╝     ",
    ),
}

WORD = "BITCRAFT"
BITCRAFT_LOGO = "\n".join(
    "".join(_GLYPHS[ch][row] for ch in WORD).rstrip() for row in range(6)
)

BITCRAFT_TAGLINE = "Bitcoin Transaction Intelligence"

# One face colour per logo row, top to bottom.
FACE_COLOURS = ("#ffe27a", "#ffd84d", "#ffc233", "#ffa700", "#ff8c42", "#fa8072")
SHADOW_COLOUR = "#6b4a1e"
TAGLINE_COLOUR = "#b8a27a"


def logo_text(show_tagline: bool = False) -> Text:
    """Rich Text for the logo with gradient faces and bronze shadows."""
    text = Text(justify="center", no_wrap=True, end="")
    for i, line in enumerate(BITCRAFT_LOGO.split("\n")):
        face = Style(color=FACE_COLOURS[i], bold=True)
        shadow = Style(color=SHADOW_COLOUR)
        for ch in line:
            text.append(ch, face if ch == "█" else shadow)
        if i < 5:
            text.append("\n")
    if show_tagline:
        text.append("\n\n")
        text.append("·  ", Style(color=SHADOW_COLOUR))
        text.append(" ".join(BITCRAFT_TAGLINE.upper()), Style(color=TAGLINE_COLOUR))
        text.append("  ·", Style(color=SHADOW_COLOUR))
    return text


class Logo(Static):
    """Centered solid-block BitCraft wordmark."""

    DEFAULT_CSS = """
    Logo {
        width: 100%;
        height: auto;
        content-align: center middle;
    }
    """

    def __init__(self, *, show_tagline: bool = False, **kwargs) -> None:
        super().__init__(logo_text(show_tagline), **kwargs)
