"""Primary driver tags from weighted score contributions.

Weights mirrored from ml/config.yaml (plans/plan.md section 7).
"""

from __future__ import annotations

from typing import Literal

from bitcraft.providers.demo_provider import (
    ANOMALY_WEIGHT,
    COMMUNITY_WEIGHT,
    MODEL_WEIGHT,
    NETWORK_WEIGHT,
)

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
