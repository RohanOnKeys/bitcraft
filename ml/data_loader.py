"""Dataset ingestion and coverage-aware master table construction.

Loads the five bitcraft_consolidated_v1 tables, validates their shapes and
dtypes against the dataset contract, and joins them into a single master
table keyed on elliptic_tx_id. Coverage flags (has_synthetic_layer,
has_network_layer) are preserved rather than inferred, and missing network
evidence is never treated as zero risk. See plans/plan.md sections 2-4.

Column names beyond the documented primary/foreign keys and the fields
named explicitly in plans/plan.md section 6.1 are inferred from the field
descriptions in section 4, since the dataset itself has not been imported
into this repository yet. Once datasets/ is populated, cross-check the
*_COLUMN constants below against datasets/metadata.json and
datasets/README.md and adjust them if the real column names differ.
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

# The two ID namespaces (plan section 2.4). They must never be merged into
# one join key; every join below joins strictly within one namespace.
ELLIPTIC_TX_ID = "elliptic_tx_id"
SYNTHETIC_TX_ID = "synthetic_transaction_id"
SYNTHETIC_TX_ID_PREFIX = "SYN_TX_"

# Provenance fields that must be carried through joins into alert evidence
# (plan section 2.3).
PROVENANCE_FIELDS = ["data_source", "generation_method", "mapping_method"]

# Synthetic-layer fields from plan section 6.1. Numeric fields get a
# neutral sentinel plus a missing indicator when absent (plan section 2.2);
# categorical fields are left null.
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
SYNTHETIC_MISSING_SENTINEL = -1

# Network aggregate inputs (plan section 4, Network layer). Column names
# are inferred from the aggregate descriptions and need verification
# against the real network.csv schema.
NETWORK_DURATION_COLUMN = "connection_duration_sec"
NETWORK_PEER_COUNT_COLUMN = "peer_count"
NETWORK_SOURCE_IP_COLUMN = "source_ip"
NETWORK_DESTINATION_IP_COLUMN = "destination_ip"
NETWORK_COUNTRY_COLUMNS = ["source_country", "destination_country"]


def _validate_shape(df: pd.DataFrame, filename: str) -> None:
    """Raise if a loaded table does not match the documented dataset shape."""
    expected = EXPECTED_SHAPES[filename]
    if df.shape != expected:
        raise ValueError(f"{filename}: expected shape {expected}, got {df.shape}")


def _require_columns(df: pd.DataFrame, filename: str, columns: list[str]) -> None:
    """Raise if any of the documented required columns are missing."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{filename}: missing required column(s) {missing}")


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the anonymized feature_* columns present in the Elliptic table."""
    return [c for c in df.columns if c.startswith("feature_")]


def load_elliptic_features(datasets_dir: Path) -> pd.DataFrame:
    """Load elliptic_features.csv and validate its shape.

    Ground-truth transaction features, keyed on elliptic_tx_id (int64).
    """
    df = pd.read_csv(datasets_dir / "elliptic_features.csv")
    _validate_shape(df, "elliptic_features.csv")
    _require_columns(
        df, "elliptic_features.csv", [ELLIPTIC_TX_ID, "timestep", "class_label"]
    )
    df[ELLIPTIC_TX_ID] = df[ELLIPTIC_TX_ID].astype("int64")
    return df


def load_transactions(datasets_dir: Path) -> pd.DataFrame:
    """Load transactions.csv (synthetic transaction layer).

    Keyed on synthetic_transaction_id (SYN_TX_* string). Values here are
    statistically representative, not observed facts about any specific
    Elliptic transaction; mapping.csv makes that link a linkage, not an
    equivalence (plan section 2.3).
    """
    df = pd.read_csv(datasets_dir / "transactions.csv")
    _validate_shape(df, "transactions.csv")
    _require_columns(df, "transactions.csv", [SYNTHETIC_TX_ID])
    df[SYNTHETIC_TX_ID] = df[SYNTHETIC_TX_ID].astype(str)
    return df


def load_network(datasets_dir: Path) -> pd.DataFrame:
    """Load network.csv (synthetic P2P network layer).

    Keyed on observation_id; multiple observations may exist per
    synthetic_transaction_id and are aggregated in build_master_table.
    """
    df = pd.read_csv(datasets_dir / "network.csv")
    _validate_shape(df, "network.csv")
    _require_columns(df, "network.csv", ["observation_id", SYNTHETIC_TX_ID])
    df[SYNTHETIC_TX_ID] = df[SYNTHETIC_TX_ID].astype(str)
    return df


def load_mapping(datasets_dir: Path) -> pd.DataFrame:
    """Load mapping.csv linking elliptic_tx_id to synthetic_transaction_id.

    This is a statistical linkage only, not a claim of correspondence
    (plan section 2.3).
    """
    df = pd.read_csv(datasets_dir / "mapping.csv")
    _validate_shape(df, "mapping.csv")
    _require_columns(df, "mapping.csv", ["mapping_id", ELLIPTIC_TX_ID, SYNTHETIC_TX_ID])
    df[ELLIPTIC_TX_ID] = df[ELLIPTIC_TX_ID].astype("int64")
    df[SYNTHETIC_TX_ID] = df[SYNTHETIC_TX_ID].astype(str)
    return df


def load_relationships(datasets_dir: Path) -> pd.DataFrame:
    """Load relationships.csv (transaction-to-transaction edges).

    source_tx_id / target_tx_id stay within a single relationship-type
    namespace per edge; they are not assumed to be elliptic_tx_id values.
    """
    df = pd.read_csv(datasets_dir / "relationships.csv")
    _validate_shape(df, "relationships.csv")
    _require_columns(
        df, "relationships.csv", ["relationship_id", "source_tx_id", "target_tx_id"]
    )
    return df


def _add_synthetic_layer(
    master: pd.DataFrame, mapping: pd.DataFrame, transactions: pd.DataFrame
) -> pd.DataFrame:
    """Join the synthetic transaction layer through mapping.csv.

    elliptic_tx_id -> mapping.csv -> synthetic_transaction_id -> transactions.csv.
    Sets has_synthetic_layer explicitly rather than inferring it from
    nulls, fills missing numeric fields with a neutral sentinel plus a
    missing indicator, and leaves missing categorical fields null.
    """
    linked = mapping.merge(transactions, on=SYNTHETIC_TX_ID, how="left")
    master = master.merge(linked, on=ELLIPTIC_TX_ID, how="left")
    master["has_synthetic_layer"] = master[SYNTHETIC_TX_ID].notna()

    for column in SYNTHETIC_NUMERIC_FIELDS:
        if column not in master.columns:
            continue
        master[f"{column}_missing"] = master[column].isna()
        master[column] = master[column].fillna(SYNTHETIC_MISSING_SENTINEL)

    return master


def _aggregate_network(network: pd.DataFrame) -> pd.DataFrame:
    """Aggregate multiple network observations per synthetic_transaction_id.

    Mean connection_duration_sec, mean peer_count, distinct source IP
    count, distinct destination IP count, distinct country count
    (plan section 4, Network layer).
    """
    country_columns = [c for c in NETWORK_COUNTRY_COLUMNS if c in network.columns]

    agg = network.groupby(SYNTHETIC_TX_ID).agg(
        mean_connection_duration_sec=(NETWORK_DURATION_COLUMN, "mean"),
        mean_peer_count=(NETWORK_PEER_COUNT_COLUMN, "mean"),
        distinct_source_ip_count=(NETWORK_SOURCE_IP_COLUMN, "nunique"),
        distinct_destination_ip_count=(NETWORK_DESTINATION_IP_COLUMN, "nunique"),
    )

    if country_columns:
        stacked = network.melt(
            id_vars=[SYNTHETIC_TX_ID], value_vars=country_columns, value_name="country"
        )
        country_counts = stacked.groupby(SYNTHETIC_TX_ID)["country"].nunique()
        agg["distinct_country_count"] = country_counts

    return agg.reset_index()


def _add_network_layer(master: pd.DataFrame, network: pd.DataFrame) -> pd.DataFrame:
    """Join aggregated network observations through synthetic_transaction_id.

    Missing network aggregates remain null (never zero-filled) and stay
    gated by has_network_layer downstream; absent network evidence must
    never be interpreted as zero risk (plan section 2.2).
    """
    agg = _aggregate_network(network)
    master = master.merge(agg, on=SYNTHETIC_TX_ID, how="left")
    master["has_network_layer"] = master["mean_connection_duration_sec"].notna()
    return master


def load_known_ranges(reference_path: Path) -> pd.DataFrame:
    """Load a reference table of known Tor-exit and hosting-provider ASNs.

    Expected columns: asn, category (one of "tor_exit", "hosting_provider").
    Path and schema are not yet part of the repository structure in
    plans/plan.md section 12; this is a placeholder for the Stage 0
    reference data described in section 5.
    """
    return pd.read_csv(reference_path)


def flag_known_infrastructure(
    master: pd.DataFrame, known_ranges: pd.DataFrame
) -> pd.DataFrame:
    """Flag source/destination ASNs that are known Tor-exit or hosting infrastructure.

    Only meaningful where has_network_layer is True. Rows without network
    coverage get False, not null: the flag is about known-bad ASNs, not
    about evidence coverage, which has_network_layer already tracks.
    """
    tor_asns = set(known_ranges.loc[known_ranges["category"] == "tor_exit", "asn"])
    hosting_asns = set(
        known_ranges.loc[known_ranges["category"] == "hosting_provider", "asn"]
    )

    for prefix in ("source_asn", "destination_asn"):
        if prefix not in master.columns:
            continue
        master[f"{prefix}_is_tor_exit"] = master[prefix].isin(tor_asns).fillna(False)
        master[f"{prefix}_is_hosting_provider"] = (
            master[prefix].isin(hosting_asns).fillna(False)
        )

    return master


def build_master_table(
    datasets_dir: Path, reference_dir: Path | None = None
) -> pd.DataFrame:
    """Build the 203,769-row master table.

    One row per elliptic_tx_id. Joins the synthetic layer through
    mapping.csv and the network layer through synthetic_transaction_id,
    sets has_synthetic_layer and has_network_layer, and flags Tor-exit /
    hosting-provider ASNs when reference_dir/known_ranges.csv is given.
    """
    features = load_elliptic_features(datasets_dir)
    mapping = load_mapping(datasets_dir)
    transactions = load_transactions(datasets_dir)
    network = load_network(datasets_dir)

    master = features.copy()
    master = _add_synthetic_layer(master, mapping, transactions)
    master = _add_network_layer(master, network)

    if reference_dir is not None:
        known_ranges_path = reference_dir / "known_ranges.csv"
        if known_ranges_path.exists():
            known_ranges = load_known_ranges(known_ranges_path)
            master = flag_known_infrastructure(master, known_ranges)

    if len(master) != EXPECTED_SHAPES["elliptic_features.csv"][0]:
        raise ValueError(
            f"master table: expected {EXPECTED_SHAPES['elliptic_features.csv'][0]} "
            f"rows (one per elliptic_tx_id), got {len(master)}"
        )

    return master
