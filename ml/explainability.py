"""SHAP explainability and provenance-tagged evidence generation.

Computes SHAP TreeExplainer values for the top-N ranked alerts only, and
builds the plain-English evidence string that serves as the primary
explanation, since Elliptic's 165 features are anonymized and have no
published semantic mapping.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# SHAP reasons kept per alert (largest absolute contribution first).
TOP_SHAP_REASONS = 5

# Provenance per evidence field: "real" comes from Elliptic features,
# labels or the observed transaction graph; "modeled" comes from the
# synthetic transaction / P2P network layers (plan section 2.3).
REAL = "real"
MODELED = "modeled"


def compute_shap_values(
    model, feature_matrix: pd.DataFrame, top_n: int, flip: bool = False
) -> pd.DataFrame:
    """Compute SHAP TreeExplainer values for the top-N ranked alerts.

    feature_matrix must already be ordered by rank (or be exactly the
    top-N rows) and hold exactly the model's input columns. Positive values
    push toward "risky": the risk model's log-odds are used as-is; pass
    flip=True for the Isolation Forest, whose output is "normality".
    """
    import shap  # local: heavy import, only needed for this stage

    rows = feature_matrix.head(top_n)
    if rows.empty:
        return pd.DataFrame(columns=feature_matrix.columns)
    explainer = shap.TreeExplainer(model)
    values = np.asarray(explainer.shap_values(rows.to_numpy()))
    if values.ndim == 3:  # some versions return one slice per class
        values = values[..., -1]
    if flip:
        values = -values
    return pd.DataFrame(values, index=rows.index, columns=feature_matrix.columns)


def top_shap_reasons(shap_row: pd.Series, n: int = TOP_SHAP_REASONS) -> list[dict]:
    """Largest |contribution| features for one alert, as JSON-ready dicts.

    feature_index is the Elliptic feature number for feature_* columns and
    -1 for engineered columns (graph, network, coverage), which keep their
    name in "feature".
    """
    ordered = shap_row.reindex(shap_row.abs().sort_values(ascending=False).index)
    reasons = []
    for name, value in ordered.head(n).items():
        index = int(name.split("_", 1)[1]) if name.startswith("feature_") and name[8:].isdigit() else -1
        reasons.append(
            {"feature": name, "feature_index": index, "contribution": round(float(value), 6)}
        )
    return reasons


def _percentile(series: pd.Series) -> pd.Series:
    """0..100 percentile rank, NaN stays NaN."""
    return (series.rank(pct=True) * 100).round(0)


def add_evidence_percentiles(master_table: pd.DataFrame) -> pd.DataFrame:
    """Attach degree / pagerank percentiles used by the evidence strings."""
    frame = master_table.copy()
    for column in ("degree", "pagerank"):
        if column in frame.columns:
            frame[f"{column}_percentile"] = _percentile(pd.to_numeric(frame[column], errors="coerce"))
    return frame


def _present(value) -> bool:
    if value is None:
        return False
    try:
        return not (isinstance(value, float) and math.isnan(value)) and not pd.isna(value)
    except (TypeError, ValueError):
        return True


def build_evidence_items(row: pd.Series, shap_reasons: list[dict] | None = None) -> list[dict]:
    """Structured evidence rows, each tagged real or modeled."""
    items: list[dict] = []

    def add(label: str, value, provenance: str) -> None:
        items.append({"label": label, "value": str(value), "provenance": provenance})

    if _present(row.get("community_size")):
        add("community size", int(row["community_size"]), REAL)
    ratio = row.get("community_illicit_ratio")
    add("community illicit ratio", f"{ratio:.2f}" if _present(ratio) else "unlabeled", REAL)
    if _present(row.get("degree_percentile")):
        add("degree percentile", int(row["degree_percentile"]), REAL)
    if _present(row.get("pagerank_percentile")):
        add("pagerank percentile", int(row["pagerank_percentile"]), REAL)
    if bool(row.get("has_network_layer", False)):
        for column, label in (
            ("distinct_source_ip_count", "distinct source IP count"),
            ("distinct_destination_ip_count", "distinct destination IP count"),
            ("distinct_country_count", "distinct country count"),
        ):
            if _present(row.get(column)):
                add(label, int(row[column]), MODELED)
        for column, label in (
            ("source_asn_is_tor_exit", "tor-exit ASN"),
            ("source_asn_is_hosting_provider", "hosting ASN"),
        ):
            if bool(row.get(column, False)):
                add(label, "yes", MODELED)
    if bool(row.get("has_synthetic_layer", False)):
        value = row.get("output_value_btc")
        if _present(value) and float(value) >= 0:
            add("output value (BTC)", f"{float(value):.4f}", MODELED)
    if shap_reasons:
        top = ", ".join(r["feature"] for r in shap_reasons[:3])
        add("top SHAP features", top, REAL)
    return items


def build_evidence_string(row: pd.Series) -> str:
    """Build a provenance-tagged, human-readable evidence string for one alert.

    Every evidence field must indicate whether it is real or modeled.
    """
    parts = [f"Rank {int(row['rank'])} alert"]
    community = row.get("community_id")
    if _present(community):
        size = row.get("community_size")
        size_txt = f", {int(size)} members" if _present(size) else ""
        ratio = row.get("community_illicit_ratio")
        ratio_txt = f"illicit ratio {ratio:.2f}" if _present(ratio) else "illicit ratio unlabeled"
        parts.append(f"in community {int(community)} ({ratio_txt}{size_txt}) [real]")
    parts_txt = " ".join(parts) + "."
    detail = []
    if _present(row.get("risk_score")):
        detail.append(f"risk model {float(row['risk_score']):.2f} [real]")
    detail.append(f"anomaly {float(row['anomaly_score']):.2f} [real]")
    if _present(row.get("degree_percentile")):
        detail.append(f"degree p{int(row['degree_percentile'])} [real]")
    if bool(row.get("has_network_layer", False)):
        countries = row.get("distinct_country_count")
        ips = row.get("distinct_source_ip_count")
        net = f"network ~{float(row.get('network_ip_signal', 0.0)):.2f}"
        if _present(countries) and _present(ips):
            net += f" ({int(ips)} IPs, {int(countries)} countries)"
        detail.append(net + " [modeled]")
    else:
        detail.append("no network evidence (not the same as low risk)")
    return parts_txt + " " + ", ".join(detail) + "."
