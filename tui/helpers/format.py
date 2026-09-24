"""Number, score bar, and glyph formatting helpers."""

from __future__ import annotations

import os


def ascii_mode() -> bool:
    """True when BITCRAFT_ASCII=1 forces plain ASCII glyphs."""
    return os.environ.get("BITCRAFT_ASCII", "").strip() == "1"


def format_int(n: int) -> str:
    """Format an integer with thousands separators."""
    return f"{n:,}"


def format_pct(value: float, digits: int = 1) -> str:
    """Format a percentage value."""
    return f"{value:.{digits}f}%"


def score_bar(score: float, width: int = 10) -> str:
    """Render a composite score as a filled bar like #######---."""
    score = max(0.0, min(1.0, score))
    filled = int(round(score * width))
    fill = "#" if ascii_mode() else "#"
    empty = "-"
    return fill * filled + empty * (width - filled)


def network_cell(has_network: bool, signal: float) -> str:
    """Render network signal: n/a when missing, else ~0.42 modeled."""
    if not has_network:
        return "n/a"
    return f"~{signal:.2f}"


def modeled_mark(text: str) -> str:
    """Prefix modeled values with the ~ glyph."""
    if text.startswith("~"):
        return text
    return f"~{text}"
