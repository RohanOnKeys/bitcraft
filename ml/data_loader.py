"""Dataset ingestion and coverage-aware master table construction.

Loads the five bitcraft_consolidated_v1 tables, validates their shapes and
dtypes against the dataset contract, and joins them into a single master
table keyed on elliptic_tx_id. Coverage flags (has_synthetic_layer,
has_network_layer) are preserved rather than inferred, and missing network
evidence is never treated as zero risk.
"""

from pathlib import Path

import pandas as pd

EXPECTED_SHAPES = {
    "elliptic_features.csv": (203_769, 170),
    "transactions.csv": (50_000, 16),
    "network.csv": (40_854, 13),
    "mapping.csv": (50_000, 6),
    "relationships.csv": (245_856, 6),
}


def load_elliptic_features(datasets_dir: Path) -> pd.DataFrame:
    """Load elliptic_features.csv and validate its shape."""
    raise NotImplementedError


def load_transactions(datasets_dir: Path) -> pd.DataFrame:
    """Load transactions.csv (synthetic transaction layer)."""
    raise NotImplementedError


def load_network(datasets_dir: Path) -> pd.DataFrame:
    """Load network.csv (synthetic P2P network layer)."""
    raise NotImplementedError


def load_mapping(datasets_dir: Path) -> pd.DataFrame:
    """Load mapping.csv linking elliptic_tx_id to synthetic_transaction_id."""
    raise NotImplementedError


def load_relationships(datasets_dir: Path) -> pd.DataFrame:
    """Load relationships.csv (transaction-to-transaction edges)."""
    raise NotImplementedError


def build_master_table(datasets_dir: Path) -> pd.DataFrame:
    """Build the 203,769-row master table.

    Joins the synthetic layer through mapping.csv and the network layer
    through synthetic_transaction_id, sets has_synthetic_layer and
    has_network_layer, and flags Tor-exit / hosting-provider ASNs.
    Missing synthetic values use a neutral sentinel with a missing
    indicator; missing network aggregates remain null and stay gated
    by has_network_layer.
    """
    raise NotImplementedError
