"""Transaction graph construction and community detection.

Builds a transaction-to-transaction graph from relationships.csv, computes
degree, PageRank, and clustering coefficient per transaction, and runs
Louvain community detection to assign community_id and community-level
illicit ratios. See plans/plan.md sections 4, 6.3, and 9.4.

relationships.csv mixes two edge namespaces (plan section 2.4): real
Elliptic edges keyed on elliptic_tx_id, and synthetic same-timestep edges
keyed on synthetic_transaction_id (plan section 15.1). The two ID types
are never merged into one join key here; graph node values are kept
exactly as they appear in relationships.csv, and only resolve_to_elliptic_tx_id
maps synthetic-keyed results back onto elliptic_tx_id, through mapping.csv,
for the master table join. Column names beyond source_tx_id/target_tx_id/
relationship_id are inferred pending verification against the real
relationships.csv schema (see ml/data_loader.py module docstring).
"""

import community as community_louvain  # python-louvain
import networkx as nx
import pandas as pd

from ml.data_loader import ELLIPTIC_TX_ID, SYNTHETIC_TX_ID, SYNTHETIC_TX_ID_PREFIX

SOURCE_COLUMN = "source_tx_id"
TARGET_COLUMN = "target_tx_id"
RELATIONSHIP_TYPE_COLUMN = "relationship_type"
DATA_SOURCE_COLUMN = "data_source"

# Raw graph node ID, before resolution to elliptic_tx_id. Distinct from
# ELLIPTIC_TX_ID so a node-id-keyed frame can never be mistaken for one
# already resolved to the master table's join key.
NODE_ID_COLUMN = "tx_node_id"

# Standard Elliptic convention: class_label 1 is illicit. Everything else
# labeled (not null) is treated as licit.
ILLICIT_CLASS_LABEL = 1


def build_graph(relationships: pd.DataFrame) -> nx.Graph:
    """Build the transaction graph from the 245,856 relationship edges.

    Node values are kept exactly as they appear in relationships.csv, not
    coerced into a shared ID space.
    """
    edge_attrs = [
        c
        for c in (RELATIONSHIP_TYPE_COLUMN, DATA_SOURCE_COLUMN)
        if c in relationships.columns
    ]
    return nx.from_pandas_edgelist(
        relationships,
        source=SOURCE_COLUMN,
        target=TARGET_COLUMN,
        edge_attr=edge_attrs or None,
    )


def compute_graph_features(graph: nx.Graph) -> pd.DataFrame:
    """Compute degree, pagerank, and clustering_coefficient per node.

    Returns one row per graph node, indexed by the raw node ID as it
    appears in relationships.csv. Use resolve_to_elliptic_tx_id to join
    this onto the master table.
    """
    degree = dict(graph.degree())
    pagerank = nx.pagerank(graph)
    clustering = nx.clustering(graph)

    features = pd.DataFrame(
        {
            NODE_ID_COLUMN: list(degree.keys()),
            "degree": list(degree.values()),
        }
    )
    features["pagerank"] = features[NODE_ID_COLUMN].map(pagerank)
    features["clustering_coefficient"] = features[NODE_ID_COLUMN].map(clustering)
    return features


def detect_communities(graph: nx.Graph) -> pd.DataFrame:
    """Run Louvain community detection and assign community_id.

    Returns one row per graph node, indexed by the raw node ID.
    """
    partition = community_louvain.best_partition(graph)
    return pd.DataFrame(
        {
            NODE_ID_COLUMN: list(partition.keys()),
            "community_id": list(partition.values()),
        }
    )


def resolve_to_elliptic_tx_id(
    node_features: pd.DataFrame, mapping: pd.DataFrame
) -> pd.DataFrame:
    """Resolve raw graph node IDs onto elliptic_tx_id for the master table join.

    Rows whose node ID is already an elliptic_tx_id pass through unchanged.
    Rows whose node ID is a synthetic_transaction_id are mapped through
    mapping.csv. That linkage is statistical, not an identity (plan
    section 2.3): it is used only to attach graph structure computed on
    the shared transaction graph, never to relabel a synthetic node as an
    observed Elliptic transaction.
    """
    node_ids = node_features[NODE_ID_COLUMN].astype(str)
    is_synthetic = node_ids.str.startswith(SYNTHETIC_TX_ID_PREFIX)

    real = node_features.loc[~is_synthetic].copy()
    real[ELLIPTIC_TX_ID] = real[NODE_ID_COLUMN].astype("int64")

    synthetic = node_features.loc[is_synthetic].copy()
    synthetic[SYNTHETIC_TX_ID] = synthetic[NODE_ID_COLUMN].astype(str)
    synthetic = synthetic.merge(
        mapping[[ELLIPTIC_TX_ID, SYNTHETIC_TX_ID]], on=SYNTHETIC_TX_ID, how="inner"
    )

    feature_columns = [c for c in node_features.columns if c != NODE_ID_COLUMN]
    resolved = pd.concat(
        [real[[ELLIPTIC_TX_ID, *feature_columns]], synthetic[[ELLIPTIC_TX_ID, *feature_columns]]],
        ignore_index=True,
    )
    return resolved.drop_duplicates(subset=ELLIPTIC_TX_ID, keep="first")


def compute_community_illicit_ratio(
    communities: pd.DataFrame, master_table: pd.DataFrame
) -> pd.DataFrame:
    """Compute community_illicit_ratio and mean_pagerank per community.

    communities must already be resolved to elliptic_tx_id (see
    resolve_to_elliptic_tx_id) and carry a community_id column. Uses only
    the labeled 22.9% subset of Elliptic transactions (class_label not
    null); this is a community-level population statistic, not a
    per-transaction ground-truth label (plan section 6.3). A community
    with no labeled members gets a null ratio, never zero, so missing
    evidence is not read as zero risk.
    """
    labeled = master_table.loc[
        master_table["class_label"].notna(), [ELLIPTIC_TX_ID, "class_label"]
    ]
    merged = communities.merge(labeled, on=ELLIPTIC_TX_ID, how="inner")

    labeled_summary = merged.groupby("community_id").agg(
        labeled_size=("class_label", "size"),
        illicit_count=(
            "class_label",
            lambda s: (s.astype(int) == ILLICIT_CLASS_LABEL).sum(),
        ),
    )
    labeled_summary["community_illicit_ratio"] = (
        labeled_summary["illicit_count"] / labeled_summary["labeled_size"]
    )

    result = communities.groupby("community_id").size().rename("size").reset_index()

    if "pagerank" in communities.columns:
        mean_pagerank = communities.groupby("community_id")["pagerank"].mean()
        result = result.merge(
            mean_pagerank.rename("mean_pagerank").reset_index(),
            on="community_id",
            how="left",
        )

    result = result.merge(
        labeled_summary["community_illicit_ratio"].reset_index(),
        on="community_id",
        how="left",
    )
    return result


def compute_modularity(graph: nx.Graph, communities: pd.DataFrame) -> float:
    """Evaluate Louvain community quality using the modularity score.

    communities must be the raw, unresolved output of detect_communities
    (keyed by tx_node_id, not elliptic_tx_id), so every graph node has a
    community assignment covering the graph exactly once.
    """
    partition = dict(zip(communities[NODE_ID_COLUMN], communities["community_id"]))
    node_sets: dict[int, set] = {}
    for node, community_id in partition.items():
        node_sets.setdefault(community_id, set()).add(node)
    return nx.algorithms.community.quality.modularity(graph, node_sets.values())
