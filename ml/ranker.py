"""Score fusion and alert ranking.

Fuses anomaly_score, community_illicit_ratio, and network_ip_signal into a
single composite_score using the weights in ml/config.yaml, and writes the
ranked alert table.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Network aggregates that feed network_ip_signal. Each is percentile-ranked
# within the network-covered population, so the signal reads "how unusual
# is this observation pattern relative to other observed transactions".
NETWORK_SIGNAL_COMPONENTS = (
    "distinct_source_ip_count",
    "distinct_destination_ip_count",
    "distinct_country_count",
    "mean_peer_count",
)
# Short connections are the suspicious end, so duration is inverted.
NETWORK_SIGNAL_INVERTED = ("mean_connection_duration_sec",)
INFRASTRUCTURE_FLAGS = (
    "source_asn_is_tor_exit",
    "destination_asn_is_tor_exit",
    "source_asn_is_hosting_provider",
    "destination_asn_is_hosting_provider",
)
# Each known Tor-exit / hosting ASN hit adds this much (capped at 1.0).
INFRASTRUCTURE_BONUS = 0.15

# Display tiers, mirrored by tui/helpers/severity.py.
SEVERITY_THRESHOLDS = (("critical", 0.80), ("high", 0.60), ("medium", 0.40))


def compute_network_ip_signal(master_table: pd.DataFrame) -> pd.Series:
    """Compute network_ip_signal, defaulting to 0 where has_network_layer is False.

    A 0 score must never be confused with unavailable network evidence;
    has_network_layer stays available downstream for that distinction.
    """
    covered = master_table["has_network_layer"].fillna(False).astype(bool)
    signal = pd.Series(0.0, index=master_table.index, name="network_ip_signal")
    if not covered.any():
        return signal

    parts: list[pd.Series] = []
    observed = master_table.loc[covered]
    for column in NETWORK_SIGNAL_COMPONENTS:
        if column in observed.columns:
            parts.append(pd.to_numeric(observed[column], errors="coerce").rank(pct=True))
    for column in NETWORK_SIGNAL_INVERTED:
        if column in observed.columns:
            parts.append(1.0 - pd.to_numeric(observed[column], errors="coerce").rank(pct=True))
    base = pd.concat(parts, axis=1).mean(axis=1).fillna(0.0) if parts else 0.0

    bonus = pd.Series(0.0, index=observed.index)
    for flag in INFRASTRUCTURE_FLAGS:
        if flag in observed.columns:
            bonus += observed[flag].fillna(False).astype(float) * INFRASTRUCTURE_BONUS

    signal.loc[covered] = (base + bonus).clip(0.0, 1.0)
    return signal


def compute_composite_score(
    anomaly_score: pd.Series,
    community_illicit_ratio: pd.Series,
    network_ip_signal: pd.Series,
    config: dict,
    risk_score: pd.Series | None = None,
) -> pd.Series:
    """Fuse the signals into composite_score using configured weights.

    risk_score (the supervised model's illicit probability) joins the plan's
    three signals when given; weights come from ml/config.yaml.

    A community with no labeled members has a null illicit ratio; it
    contributes 0 to the fusion but stays null in the stored column, so the
    UI can still say "unlabeled" rather than "low risk".
    """
    weights = config.get("score_fusion", config)
    w_anomaly = float(weights.get("anomaly_score_weight", 0.60))
    w_community = float(weights.get("community_illicit_ratio_weight", 0.25))
    w_network = float(weights.get("network_ip_signal_weight", 0.15))
    w_risk = float(weights.get("risk_model_weight", 0.0)) if risk_score is not None else 0.0
    composite = (
        w_anomaly * anomaly_score.fillna(0.0)
        + w_community * community_illicit_ratio.fillna(0.0)
        + w_network * network_ip_signal.fillna(0.0)
    )
    if w_risk:
        composite = composite + w_risk * risk_score.fillna(0.0)
    return composite.clip(0.0, 1.0).rename("composite_score")


def severity_for_score(score: float) -> str:
    """Display tier for one composite score."""
    for tier, floor in SEVERITY_THRESHOLDS:
        if score >= floor:
            return tier
    return "low"


def rank_alerts(master_table: pd.DataFrame, alert_count: int | None = None) -> pd.DataFrame:
    """Produce the final ranked alert table.

    master_table must already carry anomaly_score, community_illicit_ratio,
    network_ip_signal and composite_score. Ties break on anomaly_score, then
    elliptic_tx_id, so ranks are deterministic. alert_count keeps only the
    top N rows (the Isolation Forest contamination share by default).
    """
    ordered = master_table.sort_values(
        ["composite_score", "anomaly_score", "elliptic_tx_id"],
        ascending=[False, False, True],
        kind="mergesort",
    )
    if alert_count is not None:
        ordered = ordered.head(alert_count)
    alerts = pd.DataFrame(
        {
            "elliptic_tx_id": ordered["elliptic_tx_id"].astype("int64").to_numpy(),
            "composite_score": ordered["composite_score"].astype(float).to_numpy(),
            "anomaly_score": ordered["anomaly_score"].astype(float).to_numpy(),
            "model_score": ordered.get("risk_score", pd.Series(0.0, index=ordered.index)).astype(float).to_numpy(),
            "community_risk": ordered["community_illicit_ratio"].fillna(0.0).astype(float).to_numpy(),
            "network_signal": ordered["network_ip_signal"].astype(float).to_numpy(),
        }
    )
    alerts["rank"] = np.arange(1, len(alerts) + 1, dtype="int64")
    alerts["severity"] = alerts["composite_score"].map(severity_for_score)
    return alerts
