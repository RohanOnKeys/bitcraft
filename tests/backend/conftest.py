"""Backend test setup: fixture pipeline run loaded into a throwaway SQLite DB.

Settings are read at import time, so DATABASE_URL / ARTIFACTS_DIR are set
before the app package is imported.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_TMP = Path(tempfile.mkdtemp(prefix="bitcraft-api-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["ARTIFACTS_DIR"] = str(_TMP / "artifacts")
os.environ.pop("REDIS_URL", None)
sys.path.insert(0, str(REPO / "backend"))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.loader import load_artifacts
    from app.main import app
    from ml.pipeline import run_pipeline
    from tests.ml.fixture_data import write_fixture_dataset

    data = write_fixture_dataset(_TMP / "data")
    run_pipeline(data, REPO / "ml" / "config.yaml", _TMP / "artifacts", strict=False)
    load_artifacts(_TMP / "artifacts")
    with TestClient(app) as test_client:
        yield test_client
