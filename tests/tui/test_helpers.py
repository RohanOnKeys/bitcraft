"""Unit tests for helpers used by the TUI."""

from tui.helpers.drivers import primary_driver, weighted_parts
from tui.helpers.format import format_int, network_cell, score_bar


def test_score_bar_bounds() -> None:
    """Score bars fill the requested width."""
    assert len(score_bar(0.0, 10)) == 10
    assert len(score_bar(1.0, 10)) == 10
    assert score_bar(1.0, 5) == "#####"
    assert score_bar(0.0, 5) == "-----"


def test_network_cell_honesty() -> None:
    """Missing network evidence is n/a, never 0.00."""
    assert network_cell(False, 0.0) == "n/a"
    assert network_cell(True, 0.42) == "~0.42"


def test_format_int() -> None:
    """Thousands separators for KPI display."""
    assert format_int(203769) == "203,769"


def test_weighted_parts_sum() -> None:
    """Weighted parts use the config.yaml fusion weights."""
    parts = weighted_parts(1.0, 1.0, 1.0)
    assert abs(sum(parts.values()) - 1.0) < 1e-9
    assert primary_driver(1.0, 0.1, 0.1) == "ANOMALY"
