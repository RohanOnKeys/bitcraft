"""Business logic for reading ML pipeline job status and metrics."""

from __future__ import annotations

import json

from app.core import redis_client
from app.core.config import settings


def get_status() -> dict:
    """Return the last/running ML pipeline job status.

    Redis first (live while the pipeline runs), then the status file the
    pipeline mirrors into the artifacts directory.
    """
    raw = redis_client.get_raw(redis_client.STATUS_KEY)
    if raw:
        return json.loads(raw)
    path = settings.artifacts_dir / "pipeline_status.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"status": "unknown"}


def get_metrics() -> dict | None:
    """Validation metrics from the last run (precision@k, modularity...)."""
    path = settings.artifacts_dir / "metrics.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
