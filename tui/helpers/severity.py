"""Display-only severity tiers derived from composite_score.

These thresholds are not model outputs. They should eventually be tuned
against precision@k from ml/config.yaml (see plans/future.md).
"""

from __future__ import annotations

from tui.providers.models import SeverityTier

# Display thresholds only. Not used by the ML pipeline.
SEVERITY_THRESHOLDS: tuple[tuple[SeverityTier, float], ...] = (
    ("critical", 0.80),
    ("high", 0.60),
    ("medium", 0.40),
    ("low", 0.0),
)

SEVERITY_STYLE: dict[SeverityTier, str] = {
    "critical": "alert-high",
    "high": "alert-high",
    "medium": "alert-medium",
    "low": "alert-low",
}


def severity_for_score(composite_score: float) -> SeverityTier:
    """Map a composite score to a display severity tier."""
    for tier, floor in SEVERITY_THRESHOLDS:
        if composite_score >= floor:
            return tier
    return "low"
