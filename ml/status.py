"""Pipeline job status: Redis when reachable, always mirrored to a JSON file.

The backend's GET /pipeline/status reads the same Redis key, falling back to
the file, so status survives without Redis (local runs, tests).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REDIS_KEY = "bitcraft:pipeline:status"
STATUS_FILENAME = "pipeline_status.json"


def utc_now() -> str:
    """ISO-8601 UTC timestamp with a Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_status(output_dir: Path, payload: dict) -> None:
    """Persist the status payload to the artifacts dir and (best effort) Redis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / STATUS_FILENAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    url = os.environ.get("REDIS_URL")
    if not url:
        return
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        client.set(REDIS_KEY, json.dumps(payload))
    except Exception:  # noqa: BLE001 - status is advisory, never fail the run
        pass
