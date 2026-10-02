"""Small dataset in the bitcraft_consolidated_v1 contract, for tests.

The generator lives in ml.synthetic; tests use a few thousand rows and the
stand-in IP pools so no GeoIP database is needed.
"""

from __future__ import annotations

from pathlib import Path

from ml.synthetic import FALLBACK_POOLS as TEST_POOLS
from ml.synthetic import write_base


def write_fixture_dataset(out_dir: Path, n_tx: int = 2000, seed: int = 42, metadata: bool = False) -> Path:
    """Write the five contract CSVs (and optionally CSV metadata) into out_dir."""
    return write_base(out_dir, n_tx, seed, metadata, TEST_POOLS)
