"""Score fusion and alert ranking.

Fuses anomaly_score, community_illicit_ratio, and network_ip_signal into a
single composite_score using the weights in ml/config.yaml, and writes the
ranked alert table.
"""

import pandas as pd


def compute_network_ip_signal(master_table: pd.DataFrame) -> pd.Series:
    """Compute network_ip_signal, defaulting to 0 where has_network_layer is False.

    A 0 score must never be confused with unavailable network evidence;
    has_network_layer stays available downstream for that distinction.
    """
    raise NotImplementedError


def compute_composite_score(
    anomaly_score: pd.Series,
    community_illicit_ratio: pd.Series,
    network_ip_signal: pd.Series,
    config: dict,
) -> pd.Series:
    """Fuse the three signals into composite_score using configured weights."""
    raise NotImplementedError


def rank_alerts(master_table: pd.DataFrame) -> pd.DataFrame:
    """Produce the final ranked alert table."""
    raise NotImplementedError
