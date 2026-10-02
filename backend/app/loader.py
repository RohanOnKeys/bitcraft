"""Load ML pipeline artifacts into the API database.

    cd backend && python -m app.loader [--artifacts ../ml/artifacts]

Recreates the five tables from the Parquet files ml/pipeline.py writes,
clears cached views, and publishes the pipeline status to Redis. The API
never runs ML itself; this is the only write path.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import insert

from app.core import redis_client
from app.core.config import settings
from app.core.database import Base, engine
from app.models import Alert, AlertEvidence, Community, GraphEdge, Transaction

BATCH = 20_000


def _records(frame: pd.DataFrame) -> list[dict]:
    """DataFrame rows as plain dicts with NaN turned into None."""
    out = frame.astype(object).where(frame.notna(), None).to_dict("records")
    for row in out:
        for key, value in row.items():
            if isinstance(value, float) and math.isnan(value):
                row[key] = None
    return out


def _insert(conn, model, frame: pd.DataFrame) -> int:
    rows = _records(frame)
    for i in range(0, len(rows), BATCH):
        conn.execute(insert(model.__table__), rows[i : i + BATCH])
    return len(rows)


def _json_column(series: pd.Series) -> pd.Series:
    return series.map(lambda v: json.loads(v) if isinstance(v, str) else None)


def load_artifacts(artifacts_dir: Path) -> dict[str, int]:
    """Drop, recreate and fill every table from artifacts_dir. Returns row counts."""
    read = lambda name: pd.read_parquet(artifacts_dir / f"{name}.parquet")  # noqa: E731
    tx = read("transactions").rename(
        columns={"network_ip_signal": "network_signal", "risk_score": "model_score"}
    )
    tx["class_label"] = tx["class_label"].astype("Int64")
    tx["community_id"] = tx["community_id"].astype("Int64")
    tx["degree"] = tx["degree"].astype("Int64")
    alerts = read("alerts")
    evidence = read("evidence")
    evidence["shap_reasons"] = _json_column(evidence["shap_reasons"])
    evidence["evidence_items"] = _json_column(evidence["evidence_items"])
    edges = read("graph_edges")
    communities = read("communities")
    communities = communities[["community_id", "size", "illicit_ratio", "mean_pagerank", "alert_count"]]
    communities["mean_pagerank"] = communities["mean_pagerank"].fillna(0.0)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        counts["transactions"] = _insert(conn, Transaction, tx)
        counts["alerts"] = _insert(conn, Alert, alerts)
        counts["alert_evidence"] = _insert(conn, AlertEvidence, evidence)
        counts["communities"] = _insert(conn, Community, communities)
        counts["graph_edges"] = _insert(conn, GraphEdge, edges)

    redis_client.cache_clear()
    status_file = artifacts_dir / "pipeline_status.json"
    if status_file.exists():
        redis_client.set_raw(redis_client.STATUS_KEY, status_file.read_text(encoding="utf-8"))
    return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load ML artifacts into the BitCraft database")
    parser.add_argument("--artifacts", type=Path, default=settings.artifacts_dir)
    args = parser.parse_args(argv)
    started = time.monotonic()
    counts = load_artifacts(args.artifacts)
    for table, n in counts.items():
        print(f"{table:<16} {n:>9,}")
    print(f"loaded into {engine.url.render_as_string(hide_password=True)} in {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    main()
