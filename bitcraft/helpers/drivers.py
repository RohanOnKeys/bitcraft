"""Primary driver tags from weighted score contributions.

The weights mirror score_fusion in ml/config.yaml, so the TUI can split a
composite score into its four parts; tests/tui/test_chart.py fails if the
two ever differ.
"""

from __future__ import annotations

from typing import Literal

MODEL_WEIGHT = 0.65
ANOMALY_WEIGHT = 0.05
COMMUNITY_WEIGHT = 0.20
NETWORK_WEIGHT = 0.10

DriverTag = Literal["MODEL", "ANOMALY", "COMMUNITY", "NETWORK"]


def weighted_parts(
    anomaly: float, community: float, network: float, model: float | None = 0.0
) -> dict[DriverTag, float]:
    """Return weighted contribution of each composite component."""
    return {
        "MODEL": MODEL_WEIGHT * (model or 0.0),
        "ANOMALY": ANOMALY_WEIGHT * anomaly,
        "COMMUNITY": COMMUNITY_WEIGHT * community,
        "NETWORK": NETWORK_WEIGHT * network,
    }


def primary_driver(
    anomaly: float, community: float, network: float, model: float | None = 0.0
) -> DriverTag:
    """Component with the largest weighted contribution."""
    parts = weighted_parts(anomaly, community, network, model)
    return max(parts, key=parts.get)  # type: ignore[arg-type]
