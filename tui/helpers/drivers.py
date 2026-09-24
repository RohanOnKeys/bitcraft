"""Primary driver tags from weighted score contributions.

Weights mirrored from ml/config.yaml (plans/plan.md section 7).
"""

from __future__ import annotations

from typing import Literal

from tui.providers.demo_provider import (
    ANOMALY_WEIGHT,
    COMMUNITY_WEIGHT,
    NETWORK_WEIGHT,
)

DriverTag = Literal["ANOMALY", "COMMUNITY", "NETWORK"]


def weighted_parts(
    anomaly: float, community: float, network: float
) -> dict[DriverTag, float]:
    """Return weighted contribution of each composite component."""
    return {
        "ANOMALY": ANOMALY_WEIGHT * anomaly,
        "COMMUNITY": COMMUNITY_WEIGHT * community,
        "NETWORK": NETWORK_WEIGHT * network,
    }


def primary_driver(
    anomaly: float, community: float, network: float
) -> DriverTag:
    """Component with the largest weighted contribution."""
    parts = weighted_parts(anomaly, community, network)
    return max(parts, key=parts.get)  # type: ignore[arg-type]
