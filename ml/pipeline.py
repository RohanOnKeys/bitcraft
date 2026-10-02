"""End-to-end offline ML pipeline entry point.

Runs ingestion, graph construction, feature engineering, anomaly
detection, score fusion, and explainability in sequence, then writes
results for the backend to load. No ML code runs at API request time.

Outputs (Parquet + JSON) land in --output (default ml/artifacts):

    transactions.parquet   one row per elliptic_tx_id, with scores
    alerts.parquet         ranked alerts (top contamination share)
    evidence.parquet       evidence text/items + SHAP reasons per alert
    graph_edges.parquet    relationships resolved onto elliptic_tx_id
    communities.parquet    Louvain communities with illicit ratio
    metrics.json           precision@k, modularity, coverage, timings
    pipeline_status.json   job status (also pushed to Redis when set)

Load them into the API database with:  python -m app.loader (in backend/).
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import traceback
from pathlib import Path

import pandas as pd
import yaml

from ml import anomaly_model, explainability, graph_builder, metadata_model, ranker, risk_model, validation
from ml.data_loader import (
    ELLIPTIC_TX_ID,
    SYNTHETIC_TX_ID,
    SYNTHETIC_TX_ID_PREFIX,
    build_master_table,
    load_mapping,
    load_relationships,
)
from ml.feature_pipeline import assemble_feature_matrix
from ml.status import utc_now, write_status

log = logging.getLogger("bitcraft.pipeline")

DEFAULT_OUTPUT = Path("ml/artifacts")
GRAPH_CACHE = "graph_cache.parquet"
METADATA_FILES = ("bitcoin_metadata.csv", "bitcoin_metadata.json", "bitcoin_metadata.xml")
# Columns of the per-transaction metadata table served by the API.
TX_METADATA_COLUMNS = (
    "txid", "elliptic_tx_id", "entity_id", "timestamp", "src_ip", "src_port", "dst_ip", "dst_port",
    "src_country", "src_asn", "src_asn_org", "dst_country", "dst_asn", "dst_asn_org", "script_type",
    "n_inputs", "n_outputs", "total_in_btc", "total_out_btc", "fee", "peel_like", "peel_chain_len",
    "tor_port", "src_tor_asn", "src_hosting_asn", "cross_border", "metadata_score",
)


def _metadata_inputs(datasets_dir: Path, config: dict) -> tuple[list[Path], Path, Path] | None:
    """Metadata file(s), txid map and generator truth, if the layer exists."""
    cfg = config.get("metadata", {})
    folder = datasets_dir / cfg.get("dir", "metadata")
    if cfg.get("files"):
        files = [folder / name for name in cfg["files"]]
    else:
        files = [p for p in (folder / name for name in METADATA_FILES) if p.exists()][:1]
    txid_map = folder / cfg.get("txid_map", "txid_map.csv")
    if not files or not all(p.exists() for p in files) or not txid_map.exists():
        return None
    return files, txid_map, folder / cfg.get("truth", "generator_truth.csv")


def _graph_stage(relationships: pd.DataFrame, mapping: pd.DataFrame, cache_dir: Path, source: Path) -> tuple[pd.DataFrame, float]:
    """Graph features + Louvain communities resolved onto elliptic_tx_id.

    The slowest stage (minutes on the full graph), so the result is cached
    next to the artifacts and reused while relationships.csv and
    mapping.csv are unchanged.
    """
    stamp = "|".join(
        f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}"
        for p in (source / "relationships.csv", source / "mapping.csv")
        if p.exists()
    )
    cache = cache_dir / GRAPH_CACHE
    if cache.exists():
        cached = pd.read_parquet(cache)
        if len(cached) and cached["stamp"].iloc[0] == stamp:
            log.info("graph stage: using cache")
            return cached.drop(columns=["stamp", "modularity"]), float(cached["modularity"].iloc[0])

    graph = graph_builder.build_graph(relationships)
    node_features = graph_builder.compute_graph_features(graph)
    communities_raw = graph_builder.detect_communities(graph)
    modularity = graph_builder.community_louvain.modularity(
        dict(zip(communities_raw[graph_builder.NODE_ID_COLUMN], communities_raw["community_id"])),
        graph,
    )
    nodes = node_features.merge(communities_raw, on=graph_builder.NODE_ID_COLUMN)
    resolved = graph_builder.resolve_to_elliptic_tx_id(nodes, mapping)
    cache_dir.mkdir(parents=True, exist_ok=True)
    resolved.assign(stamp=stamp, modularity=modularity).to_parquet(cache, index=False)
    return resolved, float(modularity)


def _resolve_edges(relationships: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    """Map both edge endpoints onto elliptic_tx_id.

    Synthetic endpoints go through mapping.csv (a statistical linkage, kept
    visible through data_source / relationship_type). Unresolvable rows and
    self-loops are dropped.
    """
    syn_to_ell = dict(zip(mapping[SYNTHETIC_TX_ID].astype(str), mapping[ELLIPTIC_TX_ID].astype("int64")))

    def resolve(values: pd.Series) -> pd.Series:
        raw = values.astype("string")
        is_syn = raw.str.startswith(SYNTHETIC_TX_ID_PREFIX).fillna(False)
        out = pd.to_numeric(raw.where(~is_syn), errors="coerce")
        out[is_syn] = raw[is_syn].map(syn_to_ell)
        return out

    edges = pd.DataFrame(
        {
            "source_tx_id": resolve(relationships["source_tx_id"]),
            "target_tx_id": resolve(relationships["target_tx_id"]),
            "relationship_type": relationships.get(
                "relationship_type", pd.Series("unknown", index=relationships.index)
            ).fillna("unknown").astype(str),
            "data_source": relationships.get(
                "data_source", pd.Series("unknown", index=relationships.index)
            ).fillna("unknown").astype(str),
        }
    ).dropna(subset=["source_tx_id", "target_tx_id"])
    edges["source_tx_id"] = edges["source_tx_id"].astype("int64")
    edges["target_tx_id"] = edges["target_tx_id"].astype("int64")
    edges = edges.loc[edges["source_tx_id"] != edges["target_tx_id"]]
    return edges.drop_duplicates(subset=["source_tx_id", "target_tx_id", "relationship_type"]).reset_index(drop=True)


def run_pipeline(
    datasets_dir: Path,
    config_path: Path,
    output_dir: Path = DEFAULT_OUTPUT,
    reference_dir: Path | None = None,
    strict: bool = True,
) -> dict:
    """Run the full BitCraft ML pipeline end to end. Returns metrics."""
    started = utc_now()
    status = {"status": "running", "started_at": started, "finished_at": None, "error": None, "stage": "load"}
    write_status(output_dir, status)
    timings: dict[str, float] = {}
    t0 = time.monotonic()

    def stage(name: str) -> None:
        nonlocal t0
        now = time.monotonic()
        timings[status["stage"]] = round(now - t0, 2)
        t0 = now
        status["stage"] = name
        write_status(output_dir, status)
        log.info("stage: %s", name)

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

        master = build_master_table(datasets_dir, reference_dir, strict=strict)
        mapping = load_mapping(datasets_dir, strict)
        relationships = load_relationships(datasets_dir, strict)

        stage("graph")
        resolved, modularity = _graph_stage(relationships, mapping, output_dir, datasets_dir)
        master = master.merge(resolved, on=ELLIPTIC_TX_ID, how="left")
        # Community ratios only see labels inside the label window, so the
        # holdout metrics are not graded against labels the score already used.
        max_ts = int(config.get("label_window", {}).get("train_max_timestep", 34))
        window_labels = master[[ELLIPTIC_TX_ID, "class_label"]].assign(
            class_label=master["class_label"].where(master["timestep"] <= max_ts)
        )
        communities = graph_builder.compute_community_illicit_ratio(
            resolved[[ELLIPTIC_TX_ID, "community_id", "pagerank"]], window_labels
        )
        master = master.merge(
            communities[["community_id", "size", "community_illicit_ratio"]].rename(
                columns={"size": "community_size"}
            ),
            on="community_id",
            how="left",
        )

        stage("features")
        matrix = assemble_feature_matrix(master)

        stage("anomaly")
        model = anomaly_model.train_isolation_forest(matrix, config)
        anomaly = anomaly_model.score_anomalies(model, matrix)
        master["anomaly_score"] = master[ELLIPTIC_TX_ID].map(anomaly).fillna(0.0)

        stage("risk_model")
        indexed = master.set_index(ELLIPTIC_TX_ID)
        config.setdefault("risk_model", {}).setdefault("train_max_timestep", max_ts)
        risk, risk_scores = risk_model.train_and_score(
            matrix, indexed["class_label"], indexed["timestep"], config
        )
        master["risk_score"] = master[ELLIPTIC_TX_ID].map(risk_scores).fillna(0.0)

        stage("metadata")
        meta_inputs = _metadata_inputs(datasets_dir, config)
        meta_result = None
        if meta_inputs is not None:
            files, txid_map, truth = meta_inputs
            meta_result = metadata_model.run(
                files, txid_map, mapping,
                master[[ELLIPTIC_TX_ID, "class_label", "timestep"]].copy(), config, truth,
            )
            per_tx = meta_result.tx_scores.dropna(subset=[ELLIPTIC_TX_ID])
            score_by_ell = per_tx.groupby(ELLIPTIC_TX_ID)["metadata_score"].max()
            master["metadata_score"] = master[ELLIPTIC_TX_ID].map(score_by_ell)
        else:
            log.info("metadata layer: none found under %s, skipped", datasets_dir)
            master["metadata_score"] = float("nan")
        master["has_metadata"] = master["metadata_score"].notna()

        stage("fusion")
        master["network_ip_signal"] = ranker.compute_network_ip_signal(master)
        # The learned metadata score (IP/port/GeoIP/wallet behaviour) replaces
        # the hand-built network signal wherever a transaction has metadata.
        master["network_ip_signal"] = master["metadata_score"].where(
            master["has_metadata"], master["network_ip_signal"]
        )
        master["composite_score"] = ranker.compute_composite_score(
            master["anomaly_score"],
            master["community_illicit_ratio"],
            master["network_ip_signal"],
            config,
            risk_score=master["risk_score"],
        )
        contamination = float(config.get("isolation_forest", {}).get("contamination", 0.022))
        alert_count = max(1, round(contamination * len(master)))
        alerts = ranker.rank_alerts(master, alert_count)

        stage("explain")
        master = explainability.add_evidence_percentiles(master)
        top_n = int(config.get("explainability", {}).get("top_n_shap", 100))
        ordered_matrix = risk_model.model_features(matrix).loc[alerts[ELLIPTIC_TX_ID].head(top_n)]
        shap_frame = explainability.compute_shap_values(risk, ordered_matrix, top_n)
        by_tx = master.set_index(ELLIPTIC_TX_ID)
        evidence_rows = []
        for alert in alerts.itertuples(index=False):
            row = by_tx.loc[alert.elliptic_tx_id].copy()
            row["rank"] = alert.rank
            reasons = (
                explainability.top_shap_reasons(shap_frame.loc[alert.elliptic_tx_id])
                if alert.elliptic_tx_id in shap_frame.index
                else None
            )
            evidence_rows.append(
                {
                    ELLIPTIC_TX_ID: int(alert.elliptic_tx_id),
                    "evidence_text": explainability.build_evidence_string(row),
                    "evidence_items": json.dumps(explainability.build_evidence_items(row, reasons)),
                    "shap_reasons": json.dumps(reasons) if reasons is not None else None,
                }
            )
        evidence = pd.DataFrame(evidence_rows)

        stage("write")
        output_dir.mkdir(parents=True, exist_ok=True)
        transactions = master[
            [
                ELLIPTIC_TX_ID, "timestep", "class_label", "has_synthetic_layer", "has_network_layer", "has_metadata",
                "community_id", "degree", "pagerank", "anomaly_score", "risk_score",
                "network_ip_signal", "composite_score",
            ]
        ].copy()
        transactions["has_synthetic_layer"] = transactions["has_synthetic_layer"].fillna(False).astype(bool)
        transactions["has_network_layer"] = transactions["has_network_layer"].fillna(False).astype(bool)
        transactions["has_metadata"] = transactions["has_metadata"].astype(bool)
        if meta_result is not None:
            top_wallets = int(config.get("metadata", {}).get("entity_alerts", 500))
            wallets = metadata_model.finalise_evidence(
                meta_result, set(alerts[ELLIPTIC_TX_ID].astype(int)), top_wallets
            )
            graph = meta_result.graph
            tx_meta = graph.transactions.reindex(columns=list(TX_METADATA_COLUMNS))
            tx_meta.to_parquet(output_dir / "tx_metadata.parquet", index=False)
            graph.tx_io.to_parquet(output_dir / "tx_io.parquet", index=False)
            graph.addresses.to_parquet(output_dir / "addresses.parquet", index=False)
            graph.ips.to_parquet(output_dir / "ips.parquet", index=False)
            wallets.to_parquet(output_dir / "entities.parquet", index=False)
        transactions.to_parquet(output_dir / "transactions.parquet", index=False)
        alerts.to_parquet(output_dir / "alerts.parquet", index=False)
        evidence.to_parquet(output_dir / "evidence.parquet", index=False)
        _resolve_edges(relationships, mapping).to_parquet(output_dir / "graph_edges.parquet", index=False)
        alert_counts = alerts.merge(transactions[[ELLIPTIC_TX_ID, "community_id"]], on=ELLIPTIC_TX_ID)
        communities["alert_count"] = communities["community_id"].map(
            alert_counts.groupby("community_id").size()
        ).fillna(0).astype(int)
        communities.rename(columns={"community_illicit_ratio": "illicit_ratio"}).to_parquet(
            output_dir / "communities.parquet", index=False
        )

        stage("done")
        metrics = {
            "transactions": int(len(master)),
            "alerts": int(len(alerts)),
            "communities": int(len(communities)),
            "modularity": round(float(modularity), 4),
            "holdout": validation.holdout_report(
                master, ("composite_score", "risk_score", "anomaly_score"), max_ts + 1
            ),
            "precision_at_k": validation.precision_at_k(master),
            "coverage": {
                "labeled_pct": round(100 * float(master["class_label"].notna().mean()), 2),
                "synthetic_pct": round(100 * float(master["has_synthetic_layer"].fillna(False).mean()), 2),
                "network_pct": round(100 * float(master["has_network_layer"].fillna(False).mean()), 2),
            },
            "feature_count": int(matrix.shape[1]),
            "metadata": meta_result.metrics if meta_result is not None else None,
            "timings_s": timings,
        }
        (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        status.update(status="complete", finished_at=utc_now(), stage="done")
        write_status(output_dir, status)
        return metrics
    except Exception as exc:
        status.update(status="failed", finished_at=utc_now(), error=f"{type(exc).__name__}: {exc}")
        write_status(output_dir, status)
        log.error("pipeline failed\n%s", traceback.format_exc())
        raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the BitCraft ML pipeline")
    parser.add_argument("--datasets", type=Path, default=Path("datasets"))
    parser.add_argument("--config", type=Path, default=Path("ml/config.yaml"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reference", type=Path, default=None, help="dir with known_ranges.csv")
    parser.add_argument("--no-strict", action="store_true", help="skip exact dataset shape checks")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    metrics = run_pipeline(args.datasets, args.config, args.output, args.reference, strict=not args.no_strict)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
