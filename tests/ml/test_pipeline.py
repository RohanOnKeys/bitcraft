"""End-to-end pipeline run on the fixture dataset."""

import json
from pathlib import Path

import pandas as pd
import pytest

from ml.pipeline import run_pipeline
from tests.ml.fixture_data import write_fixture_dataset

CONFIG = Path(__file__).resolve().parents[2] / "ml" / "config.yaml"


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory) -> Path:
    data = write_fixture_dataset(tmp_path_factory.mktemp("data"), metadata=True)
    out = tmp_path_factory.mktemp("artifacts")
    run_pipeline(data, CONFIG, out, strict=False)
    return out


def test_writes_every_artifact(artifacts: Path) -> None:
    for name in (
        "transactions.parquet", "alerts.parquet", "evidence.parquet",
        "graph_edges.parquet", "communities.parquet", "metrics.json", "pipeline_status.json",
    ):
        assert (artifacts / name).is_file(), name
    status = json.loads((artifacts / "pipeline_status.json").read_text())
    assert status["status"] == "complete"


def test_alerts_are_ranked_and_bounded(artifacts: Path) -> None:
    alerts = pd.read_parquet(artifacts / "alerts.parquet")
    assert list(alerts["rank"]) == list(range(1, len(alerts) + 1))
    assert alerts["composite_score"].is_monotonic_decreasing
    assert alerts["composite_score"].between(0, 1).all()
    assert len(alerts) == round(0.022 * 2000)


def test_missing_network_is_zero_signal_but_flagged(artifacts: Path) -> None:
    tx = pd.read_parquet(artifacts / "transactions.parquet")
    # No network observation and no metadata: zero signal, but still flagged.
    uncovered = tx.loc[~tx["has_network_layer"] & ~tx["has_metadata"]]
    assert len(uncovered) > 0
    assert (uncovered["network_ip_signal"] == 0).all()


def test_ranking_beats_random_on_labels(artifacts: Path) -> None:
    metrics = json.loads((artifacts / "metrics.json").read_text())
    p = metrics["precision_at_k"]
    assert p["50"] > p["base_rate"] * 2


def test_evidence_is_provenance_tagged(artifacts: Path) -> None:
    evidence = pd.read_parquet(artifacts / "evidence.parquet")
    items = json.loads(evidence.iloc[0]["evidence_items"])
    assert items and all(i["provenance"] in {"real", "modeled"} for i in items)
    reasons = json.loads(evidence.iloc[0]["shap_reasons"])
    assert len(reasons) == 5 and {"feature", "feature_index", "contribution"} <= set(reasons[0])


def test_edges_resolve_to_elliptic_ids(artifacts: Path) -> None:
    edges = pd.read_parquet(artifacts / "graph_edges.parquet")
    assert edges["source_tx_id"].dtype == "int64"
    assert set(edges["data_source"]) <= {"elliptic", "synthetic"}


def test_holdout_metrics_and_risk_model(artifacts: Path) -> None:
    metrics = json.loads((artifacts / "metrics.json").read_text())
    holdout = metrics["holdout"]
    assert holdout["_window"]["min_timestep"] == 35
    assert holdout["risk_score"]["auc"] > 0.8
    tx = pd.read_parquet(artifacts / "transactions.parquet")
    assert tx["risk_score"].between(0, 1).all()


def test_metadata_layer_artifacts(artifacts: Path) -> None:
    wallets = pd.read_parquet(artifacts / "entities.parquet")
    assert list(wallets["rank"].head(3)) == [1, 2, 3]
    top = wallets.iloc[0]
    items = json.loads(top["evidence_items"])
    assert items and all(i["provenance"] in {"real", "modeled"} for i in items)
    tx_meta = pd.read_parquet(artifacts / "tx_metadata.parquet")
    assert {"src_ip", "src_port", "dst_port", "txid", "entity_id", "metadata_score"} <= set(tx_meta.columns)
    io = pd.read_parquet(artifacts / "tx_io.parquet")
    assert set(io["direction"]) == {"in", "out"}
    metrics = json.loads((artifacts / "metrics.json").read_text())["metadata"]
    assert metrics["ingest"]["rows_rejected"] == 0
    assert "cluster_purity" in metrics["injected_recovery"]
    tx = pd.read_parquet(artifacts / "transactions.parquet")
    assert tx["has_metadata"].any() and not tx["has_metadata"].all()
