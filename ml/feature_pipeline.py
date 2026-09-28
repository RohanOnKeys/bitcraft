"""Coverage-aware feature matrix assembly.

Assembles the approximately 183-dimension feature matrix from Elliptic
features, graph features, synthetic-layer fields, network aggregates, and
coverage flags, ready for Isolation Forest scoring.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EXCLUDED_COLUMNS = [
    "class_label",
    "synthetic_transaction_id",
    "mapping_id",
    "observation_id",
    "relationship_id",
    "tx_node_id",
    "data_source",
    "generation_method",
    "mapping_method",
    "timestamp",
    "block_number",
    "mapping_type",
]

SYNTHETIC_NUMERIC_FIELDS = [
    "input_count",
    "output_count",
    "input_value_btc",
    "output_value_btc",
    "fee_btc",
]

SYNTHETIC_CATEGORICAL_FIELDS = [
    "source_country",
    "source_asn",
    "destination_country",
    "destination_asn",
]

GRAPH_FEATURE_COLUMNS = [
    "degree",
    "pagerank",
    "clustering_coefficient",
    "community_id",
]

NETWORK_AGGREGATE_FIELDS = [
    "mean_connection_duration_sec",
    "mean_peer_count",
    "distinct_source_ip_count",
    "distinct_destination_ip_count",
    "distinct_country_count",
]

COVERAGE_COLUMNS = ["has_synthetic_layer", "has_network_layer"]

INFRASTRUCTURE_FLAG_COLUMNS = [
    "source_asn_is_tor_exit",
    "source_asn_is_hosting_provider",
    "destination_asn_is_tor_exit",
    "destination_asn_is_hosting_provider",
]


def _encode_categorical(series: pd.Series) -> pd.Series:
    """Convert categorical text columns to a numeric code and keep missing = -1."""
    values = series.astype("string")
    codes = pd.Categorical(values).codes.astype(float)
    result = pd.Series(codes, index=series.index, name=series.name)
    result = result.mask(values.isna(), -1.0)
    return result


def _coerce_numeric(series: pd.Series, fill_value: float) -> pd.Series:
    """Normalize numeric columns to float64 without leaving missing values behind."""
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    return numeric.fillna(fill_value)


def assemble_feature_matrix(master_table: pd.DataFrame) -> pd.DataFrame:
    """Assemble the full-coverage feature matrix from the master table."""
    frame = master_table.copy()

    if "elliptic_tx_id" in frame.columns:
        frame = frame.set_index("elliptic_tx_id")

    allowed_columns = {
        col for col in frame.columns if col.startswith("feature_")
    }
    allowed_columns |= {
        "timestep",
        *SYNTHETIC_NUMERIC_FIELDS,
        *SYNTHETIC_CATEGORICAL_FIELDS,
        *GRAPH_FEATURE_COLUMNS,
        *NETWORK_AGGREGATE_FIELDS,
        *COVERAGE_COLUMNS,
        *INFRASTRUCTURE_FLAG_COLUMNS,
    }
    allowed_columns |= {col for col in frame.columns if col.endswith("_missing")}

    result: dict[str, pd.Series] = {}

    for column in sorted(frame.columns):
        if column not in allowed_columns or column in EXCLUDED_COLUMNS:
            continue

        values = frame[column]

        if column in SYNTHETIC_CATEGORICAL_FIELDS:
            result[column] = _encode_categorical(values)
            continue

        if pd.api.types.is_bool_dtype(values):
            result[column] = values.astype(float)
            continue

        if column in GRAPH_FEATURE_COLUMNS and column == "community_id":
            result[column] = _coerce_numeric(values, -1.0)
            continue

        if column in GRAPH_FEATURE_COLUMNS:
            result[column] = _coerce_numeric(values, 0.0)
            continue

        if column.endswith("_missing"):
            result[column] = values.astype(bool).astype(float)
            continue

        result[column] = _coerce_numeric(values, 0.0)

    matrix = pd.DataFrame(result)
    if matrix.empty:
        return matrix

    if matrix.index.name != "elliptic_tx_id":
        matrix.index.name = "elliptic_tx_id"

    matrix = matrix.astype(np.float64) if hasattr(matrix, "astype") else matrix
    matrix = matrix.fillna(0.0)
    matrix = matrix.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return matrix.astype("float64")
