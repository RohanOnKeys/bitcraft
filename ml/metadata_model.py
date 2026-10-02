"""Metadata layer: ingest -> GeoIP -> entity graph -> model -> wallet alerts.

Learns from the correlated network-layer (IP, port, GeoIP country/ASN,
timing) and blockchain-layer (addresses, amounts, fee, script) fields of
each transaction, plus its wallet entity's behaviour. Labels come from the
linked Elliptic transaction (txid -> synthetic id -> elliptic_tx_id), under
the same label window and out-of-fold scoring as the main risk model.

Wallet alerts rank clustered entities by
    entity_risk = 0.6 * max(tx scores) + 0.4 * shrunk_mean(tx scores)
where shrunk_mean = (sum + PRIOR_WEIGHT * PRIOR) / (n + PRIOR_WEIGHT) pulls
wallets with little activity toward the base rate, so a sustained pattern
across many transactions outranks a single risky one. Each alert carries
provenance-tagged evidence and SHAP reasons from its riskiest transaction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ml import entity_graph, explainability, risk_model, validation
from ml.geoip import GeoIP
from ml.ingest import ingest
from ml.ranker import severity_for_score

MODELED = "modeled"
# Shrinkage of a wallet's mean score toward the base rate (see module doc).
PRIOR = 0.05
PRIOR_WEIGHT = 1.0


@dataclass
class MetadataResult:
    graph: entity_graph.EntityGraph
    tx_scores: pd.DataFrame  # txid, elliptic_tx_id, metadata_score, metadata_anomaly
    entities: pd.DataFrame  # ranked wallet entities with evidence
    metrics: dict = field(default_factory=dict)
    ingest_report: dict = field(default_factory=dict)


def _link(meta: pd.DataFrame, txid_map: pd.DataFrame, mapping: pd.DataFrame) -> pd.Series:
    """txid -> elliptic_tx_id through the two linkage tables."""
    linked = txid_map.merge(mapping[["synthetic_transaction_id", "elliptic_tx_id"]], on="synthetic_transaction_id")
    return meta["txid"].map(dict(zip(linked["txid"], linked["elliptic_tx_id"])))


def _entity_evidence(row: pd.Series, reasons: list[dict] | None) -> tuple[list[dict], str]:
    items: list[dict] = []

    def add(label: str, value) -> None:
        items.append({"label": label, "value": str(value), "provenance": MODELED})

    add("addresses (common-input cluster)", int(row["n_addresses"]))
    add("transactions", f"{int(row['n_txs'])} · {row['total_in_btc']:.4f} BTC in")
    add("source IPs / countries", f"{int(row['distinct_src_ips'])} / {int(row['distinct_src_countries'])}")
    if row["countries_per_day"] >= 0.5 and row["distinct_src_countries"] >= 3:
        add("country hops per day", f"{row['countries_per_day']:.2f}")
    if row["tor_share"] > 0:
        add("Tor egress share", f"{row['tor_share']:.0%}")
    if row["hosting_share"] > 0:
        add("hosting egress share", f"{row['hosting_share']:.0%}")
    if row["peel_chain_max"] >= 2:
        add("longest peeling chain", int(row["peel_chain_max"]))
    if row["round_output_share"] >= 0.3:
        add("round-amount outputs", f"{row['round_output_share']:.0%}")
    if row["input_reuse_share"] >= 0.3:
        add("address reuse on inputs", f"{row['input_reuse_share']:.0%}")
    if row.get("linked_alerts", 0):
        items.append({"label": "linked Elliptic alerts", "value": str(int(row["linked_alerts"])), "provenance": "real"})
    if reasons:
        add("top model features", ", ".join(r["feature"] for r in reasons[:3]))

    parts = [f"Wallet cluster of {int(row['n_addresses'])} addresses, {int(row['n_txs'])} transactions"]
    flags = []
    if row["distinct_src_countries"] >= 3:
        flags.append(f"IPs in {int(row['distinct_src_countries'])} countries")
    if row["tor_share"] >= 0.2:
        flags.append(f"{row['tor_share']:.0%} via Tor")
    if row["peel_chain_max"] >= 2:
        flags.append(f"peeling chain of {int(row['peel_chain_max'])}")
    if row["round_output_share"] >= 0.3:
        flags.append("round payouts")
    text = parts[0] + (": " + ", ".join(flags) if flags else "") + f". Risk {row['risk_score']:.2f} [modeled]."
    return items, text


def _recovery(graph: entity_graph.EntityGraph, entities: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """How well injected typologies and owners are recovered (synthetic truth)."""
    tx = graph.transactions.set_index("txid").join(truth.set_index("txid"), how="inner")
    if tx.empty:
        return {}
    owner_purity = tx.groupby("entity_id")["owner_id"].agg(lambda s: s.value_counts(normalize=True).iloc[0])
    weights = tx.groupby("entity_id").size()
    illicit_entity = tx.groupby("entity_id")["owner_illicit"].mean() >= 0.5
    ranked = entities.sort_values("rank")
    out = {
        "true_owners": int(truth["owner_id"].nunique()),
        "spending_entities": int(tx["entity_id"].nunique()),
        "cluster_purity": round(float((owner_purity * weights).sum() / weights.sum()), 4),
        "peel_detection": {
            "precision": round(float(tx.loc[tx["peel_like"], "peel_chain"].mean()), 4),
            "recall": round(float(tx.loc[tx["peel_chain"], "peel_like"].mean()), 4) if tx["peel_chain"].any() else None,
        },
        "tor_detection_recall": round(float((tx.loc[tx["egress"] == "tor", "src_tor_asn"] | tx.loc[tx["egress"] == "tor", "tor_port"]).mean()), 4)
        if (tx["egress"] == "tor").any() else None,
        "illicit_entity_base_rate": round(float(illicit_entity.mean()), 4),
    }
    for k in (50, 100, 500):
        top = ranked.head(k)["entity_id"]
        out[f"wallet_alert_precision@{k}"] = round(float(illicit_entity.reindex(top).fillna(False).mean()), 4)
    return out


def run(
    meta_paths,
    txid_map_path: Path,
    mapping: pd.DataFrame,
    labels: pd.DataFrame,
    config: dict,
    truth_path: Path | None = None,
) -> MetadataResult:
    """Full metadata stage. labels: elliptic_tx_id, class_label, timestep."""
    cfg = config.get("metadata", {})
    meta, report = ingest(meta_paths)
    geo = GeoIP(Path(cfg.get("geoip_dir", "datasets/geoip")))
    meta = geo.enrich(meta)
    graph = entity_graph.build(meta)
    X = entity_graph.feature_matrix(graph)

    txid_map = pd.read_csv(txid_map_path)
    tx = graph.transactions
    tx["elliptic_tx_id"] = _link(tx, txid_map, mapping).astype("Int64")
    by_ell = labels.set_index("elliptic_tx_id")
    class_label = tx.set_index("txid")["elliptic_tx_id"].map(by_ell["class_label"])
    timestep = tx.set_index("txid")["elliptic_tx_id"].map(by_ell["timestep"])

    model, scores = risk_model.train_and_score(X, class_label, timestep, config, section="metadata_model")
    iso = IsolationForest(n_estimators=200, random_state=42, n_jobs=-1).fit(X.to_numpy())
    raw = -iso.decision_function(X.to_numpy())
    anomaly = (raw - raw.min()) / (raw.max() - raw.min() or 1.0)
    tx_scores = pd.DataFrame(
        {
            "txid": X.index,
            "elliptic_tx_id": tx.set_index("txid").loc[X.index, "elliptic_tx_id"].to_numpy(),
            "metadata_score": scores.to_numpy(),
            "metadata_anomaly": anomaly,
        }
    )
    tx["metadata_score"] = tx["txid"].map(dict(zip(tx_scores["txid"], tx_scores["metadata_score"])))

    # Wallet entities: blend of their riskiest and typical transaction.
    agg = tx.groupby("entity_id")["metadata_score"].agg(["max", "sum", "count"])
    entities = graph.entities.set_index("entity_id").join(agg)
    shrunk = (entities["sum"] + PRIOR_WEIGHT * PRIOR) / (entities["count"] + PRIOR_WEIGHT)
    entities["risk_score"] = (0.6 * entities["max"] + 0.4 * shrunk).clip(0, 1)
    entities = entities.drop(columns=["max", "sum", "count"]).sort_values(
        ["risk_score", "n_txs"], ascending=[False, False], kind="mergesort"
    )
    entities["rank"] = np.arange(1, len(entities) + 1)
    entities["severity"] = entities["risk_score"].map(severity_for_score)
    worst_tx = tx.sort_values("metadata_score", ascending=False).drop_duplicates("entity_id").set_index("entity_id")["txid"]
    entities["top_txid"] = worst_tx.reindex(entities.index)
    entities["linked_alerts"] = 0

    top_n = int(cfg.get("entity_alerts", 500))
    head = entities.head(top_n)
    shap_rows = risk_model.model_features(X).loc[head["top_txid"].dropna().unique()]
    shap_frame = explainability.compute_shap_values(model, shap_rows, len(shap_rows))
    entities["shap_reasons"] = None
    entities["evidence_items"] = None
    entities["evidence_text"] = ""
    entities = entities.reset_index()

    metrics: dict = {
        "ingest": report.summary(),
        "geoip": {
            "src_country_resolved": round(float(meta["src_country"].notna().mean()), 4),
            "src_asn_resolved": round(float(meta["src_asn"].notna().mean()), 4),
            "source": meta["geo_source"].iloc[0] if len(meta) else None,
        },
        "graph": {
            "transactions": int(len(tx)),
            "addresses": int(len(graph.addresses)),
            "source_ips": int(len(graph.ips)),
            "spending_entities": int(len(graph.entities)),
        },
    }
    max_ts = int(config.get("label_window", {}).get("train_max_timestep", 34))
    scored = pd.DataFrame(
        {"class_label": class_label.to_numpy(), "timestep": timestep.to_numpy(),
         "metadata_score": scores.to_numpy(), "metadata_anomaly": anomaly}
    )
    metrics["holdout"] = validation.holdout_report(scored, ("metadata_score", "metadata_anomaly"), max_ts + 1)
    if truth_path is not None and Path(truth_path).exists():
        metrics["injected_recovery"] = _recovery(graph, entities, pd.read_csv(truth_path))

    result = MetadataResult(graph, tx_scores, entities, metrics, report.summary())
    result.shap_frame = shap_frame  # type: ignore[attr-defined]
    return result


def finalise_evidence(result: MetadataResult, alerted_elliptic: set[int], top_n: int) -> pd.DataFrame:
    """Attach linked-alert counts, evidence and SHAP reasons to the top wallets."""
    tx = result.graph.transactions
    linked = tx.loc[tx["elliptic_tx_id"].isin(alerted_elliptic)].groupby("entity_id").size()
    entities = result.entities.copy()
    entities["linked_alerts"] = entities["entity_id"].map(linked).fillna(0).astype(int)
    shap_frame = getattr(result, "shap_frame", pd.DataFrame())
    items_col, text_col, shap_col = [], [], []
    for i, row in entities.iterrows():
        if i >= top_n:
            items_col.append(None)
            text_col.append("")
            shap_col.append(None)
            continue
        reasons = (
            explainability.top_shap_reasons(shap_frame.loc[row["top_txid"]])
            if row["top_txid"] in shap_frame.index else None
        )
        items, text = _entity_evidence(row, reasons)
        items_col.append(json.dumps(items))
        text_col.append(text)
        shap_col.append(json.dumps(reasons) if reasons else None)
    entities["evidence_items"] = items_col
    entities["evidence_text"] = text_col
    entities["shap_reasons"] = shap_col
    entities["countries"] = entities["countries"].map(lambda c: json.dumps(list(c)) if isinstance(c, (list, np.ndarray)) else "[]")
    return entities
