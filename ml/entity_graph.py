"""Entity graph over IPs, wallet addresses and transactions.

Nodes: transactions (txid), addresses, source IPs. Edges:
    address --input--> tx --output--> address,   ip --relayed--> tx

Wallet clustering uses the common-input-ownership heuristic: addresses spent
together as inputs of one transaction belong to the same entity (union-find).
CoinJoin-style transactions break that assumption and can merge unrelated
owners; that is the known weakness of the heuristic and is measured against
the generator's ground truth in validation.

Builds per-transaction features (amount shape, script, ports, Tor/hosting
egress, geography, reuse, peeling chains, IP fan-out) and per-entity
aggregates that feed the metadata model and the wallet alerts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ml.addresses import SCRIPT_TYPES, script_type_of

KNOWN_RANGES = Path(__file__).resolve().parent / "reference" / "known_ranges.csv"
P2P_PORT = 8333
TOR_PORTS = (9050, 9150)
# A peel step: one input, two outputs, the smaller output under this share.
PEEL_SMALL_SHARE = 0.2


class UnionFind:
    """Disjoint sets over hashable items, with path halving."""

    def __init__(self) -> None:
        self.parent: dict = {}

    def find(self, item):
        parent = self.parent.setdefault(item, item)
        while parent != item:
            grand = self.parent.setdefault(parent, parent)
            self.parent[item] = grand
            item, parent = parent, grand
        return item

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


@dataclass
class EntityGraph:
    """Everything derived from the ingested metadata."""

    transactions: pd.DataFrame  # one row per txid with features + entity_id
    tx_io: pd.DataFrame  # txid, address, direction, amount, position
    addresses: pd.DataFrame  # address, entity_id, script_type, counts, first/last seen
    entities: pd.DataFrame  # one row per spending entity with aggregates
    ips: pd.DataFrame  # one row per source IP


def explode_io(meta: pd.DataFrame) -> pd.DataFrame:
    """Long table of every input and output (txid, address, direction, amount)."""
    parts = []
    for direction, addr_col, amt_col in (
        ("in", "input_addresses", "input_amounts"),
        ("out", "output_addresses", "output_amounts"),
    ):
        frame = meta[["txid", "timestamp", addr_col, amt_col]].rename(
            columns={addr_col: "address", amt_col: "amount"}
        )
        frame = frame.explode(["address", "amount"], ignore_index=True)
        frame["position"] = frame.groupby("txid").cumcount()
        frame["direction"] = direction
        parts.append(frame)
    io = pd.concat(parts, ignore_index=True)
    io["amount"] = io["amount"].astype(float)
    return io[["txid", "timestamp", "address", "direction", "amount", "position"]]


def cluster_addresses(io: pd.DataFrame) -> pd.Series:
    """address -> entity_id via common-input ownership (union-find)."""
    uf = UnionFind()
    for _, group in io.loc[io["direction"] == "in"].groupby("txid")["address"]:
        addresses = group.tolist()
        first = addresses[0]
        uf.find(first)
        for other in addresses[1:]:
            uf.union(first, other)
    for address in io["address"].unique():
        uf.find(address)
    roots = {address: uf.find(address) for address in io["address"].unique()}
    root_ids = {root: i for i, root in enumerate(sorted(set(roots.values())))}
    return pd.Series({a: root_ids[r] for a, r in roots.items()}, name="entity_id")


def _round_share(amounts: list[float]) -> float:
    if not amounts:
        return 0.0
    rounded = [abs(a * 100 - round(a * 100)) < 1e-6 for a in amounts]
    return float(np.mean(rounded))


def _peel_chains(meta: pd.DataFrame, peel_like: pd.Series) -> pd.Series:
    """Length of the peeling chain ending at each transaction (0 if not a peel)."""
    produced_by: dict[str, str] = {}
    chain: dict[str, int] = {}
    for row in meta.itertuples(index=False):
        length = 0
        if peel_like.get(row.txid, False):
            parent = produced_by.get(row.input_addresses[0])
            length = chain.get(parent, 0) + 1
        chain[row.txid] = length
        for address in row.output_addresses:
            produced_by[address] = row.txid
    return pd.Series(chain, name="peel_chain_len")


def build(meta: pd.DataFrame, known_ranges: Path = KNOWN_RANGES) -> EntityGraph:
    """Cluster wallets and compute transaction / entity / IP features.

    meta is the ingested (and GeoIP-enriched) metadata table, ordered by
    timestamp.
    """
    meta = meta.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    io = explode_io(meta)
    entity_of = cluster_addresses(io)
    io["entity_id"] = io["address"].map(entity_of)

    known = pd.read_csv(known_ranges)
    tor_asns = set(known.loc[known["category"] == "tor_exit", "asn"].astype(int))
    hosting_asns = set(known.loc[known["category"] == "hosting_provider", "asn"].astype(int))

    tx = meta.copy()
    tx["entity_id"] = tx["input_addresses"].map(lambda xs: entity_of[xs[0]])
    tx["n_inputs"] = tx["input_addresses"].map(len)
    tx["n_outputs"] = tx["output_addresses"].map(len)
    tx["total_in_btc"] = tx["input_amounts"].map(sum)
    tx["total_out_btc"] = tx["output_amounts"].map(sum)
    tx["fee_rate"] = tx["fee"] / tx["total_in_btc"].where(tx["total_in_btc"] > 0)
    tx["max_output_share"] = tx.apply(
        lambda r: max(r.output_amounts) / r.total_out_btc if r.total_out_btc > 0 else 0.0, axis=1
    )
    tx["min_output_share"] = tx.apply(
        lambda r: min(r.output_amounts) / r.total_out_btc if r.total_out_btc > 0 else 0.0, axis=1
    )
    tx["round_output_share"] = tx["output_amounts"].map(_round_share)
    tx["peel_like"] = (tx["n_inputs"] == 1) & (tx["n_outputs"] == 2) & (tx["min_output_share"] < PEEL_SMALL_SHARE)
    tx["peel_chain_len"] = tx["txid"].map(_peel_chains(tx, tx.set_index("txid")["peel_like"]))
    script = tx["script_type"].fillna(tx["input_addresses"].map(lambda xs: script_type_of(xs[0])))
    for name in SCRIPT_TYPES:
        tx[f"script_{name}"] = (script == name).astype(float)
    tx["tor_port"] = tx["src_port"].isin(TOR_PORTS)
    tx["nonstandard_dst_port"] = tx["dst_port"] != P2P_PORT
    src_asn = tx.get("src_asn", pd.Series(pd.NA, index=tx.index))
    tx["src_tor_asn"] = src_asn.isin(tor_asns)
    tx["src_hosting_asn"] = src_asn.isin(hosting_asns)
    if "src_country" in tx.columns and "dst_country" in tx.columns:
        tx["cross_border"] = tx["src_country"].notna() & (tx["src_country"] != tx["dst_country"])
    else:
        tx["cross_border"] = False
    tx["hour_utc"] = tx["timestamp"].dt.hour

    # Address reuse: inputs whose address is spent in more than one transaction.
    spends = io.loc[io["direction"] == "in"].groupby("address")["txid"].nunique()
    tx["input_reuse_share"] = tx["input_addresses"].map(lambda xs: float(np.mean([spends.get(a, 0) > 1 for a in xs])))

    # IP fan-out: how many distinct wallets share one source IP.
    ip_entities = tx.groupby("src_ip")["entity_id"].nunique()
    ip_txs = tx.groupby("src_ip")["txid"].size()
    tx["ip_entity_fanout"] = tx["src_ip"].map(ip_entities)
    tx["ip_tx_count"] = tx["src_ip"].map(ip_txs)

    # Entity aggregates, joined back onto each transaction.
    addresses_per_entity = io.groupby("entity_id")["address"].nunique()
    days = tx.groupby("entity_id")["timestamp"].agg(lambda s: max(1.0, (s.max() - s.min()).total_seconds() / 86400))
    grouped = tx.groupby("entity_id")
    entities = pd.DataFrame(
        {
            "n_addresses": addresses_per_entity.reindex(grouped.size().index),
            "n_txs": grouped.size(),
            "total_in_btc": grouped["total_in_btc"].sum(),
            "total_out_btc": grouped["total_out_btc"].sum(),
            "distinct_src_ips": grouped["src_ip"].nunique(),
            "distinct_src_countries": grouped["src_country"].nunique() if "src_country" in tx else 0,
            "tor_share": grouped.apply(lambda g: float((g["tor_port"] | g["src_tor_asn"]).mean())),
            "hosting_share": grouped["src_hosting_asn"].mean(),
            "peel_chain_max": grouped["peel_chain_len"].max(),
            "round_output_share": grouped["round_output_share"].mean(),
            "input_reuse_share": grouped["input_reuse_share"].mean(),
            "first_seen": grouped["timestamp"].min(),
            "last_seen": grouped["timestamp"].max(),
        }
    )
    entities["countries_per_day"] = entities["distinct_src_countries"] / days.reindex(entities.index)
    if "src_country" in tx:
        entities["countries"] = grouped["src_country"].agg(lambda s: sorted(s.dropna().unique().tolist()))
    entities.index.name = "entity_id"
    for column in ("n_addresses", "n_txs", "distinct_src_ips", "distinct_src_countries",
                   "tor_share", "countries_per_day", "peel_chain_max"):
        tx[f"entity_{column}"] = tx["entity_id"].map(entities[column])

    first_last = io.groupby("address")["timestamp"].agg(["min", "max"])
    counts = io.pivot_table(index="address", columns="direction", values="txid", aggfunc="nunique", fill_value=0)
    addresses = pd.DataFrame(
        {
            "entity_id": entity_of,
            "script_type": entity_of.index.map(script_type_of),
            "n_tx_in": counts.get("in", pd.Series(dtype=int)).reindex(entity_of.index, fill_value=0),
            "n_tx_out": counts.get("out", pd.Series(dtype=int)).reindex(entity_of.index, fill_value=0),
            "first_seen": first_last["min"].reindex(entity_of.index),
            "last_seen": first_last["max"].reindex(entity_of.index),
        }
    )
    addresses.index.name = "address"

    ip_cols = {"n_txs": ("txid", "size"), "n_entities": ("entity_id", "nunique")}
    ips = tx.groupby("src_ip").agg(**ip_cols)
    for column in ("src_country", "src_asn", "src_asn_org"):
        if column in tx.columns:
            ips[column.removeprefix("src_")] = tx.groupby("src_ip")[column].first()
    ips["tor_asn"] = tx.groupby("src_ip")["src_tor_asn"].any()
    ips["hosting_asn"] = tx.groupby("src_ip")["src_hosting_asn"].any()
    ips.index.name = "ip"

    return EntityGraph(
        transactions=tx,
        tx_io=io[["txid", "address", "direction", "amount", "position", "entity_id"]],
        addresses=addresses.reset_index(),
        entities=entities.reset_index(),
        ips=ips.reset_index(),
    )


# Numeric transaction features the metadata model learns from.
TX_FEATURES = (
    "n_inputs", "n_outputs", "total_in_btc", "total_out_btc", "fee", "fee_rate",
    "max_output_share", "min_output_share", "round_output_share", "peel_like", "peel_chain_len",
    *[f"script_{name}" for name in SCRIPT_TYPES],
    "tor_port", "nonstandard_dst_port", "src_tor_asn", "src_hosting_asn", "cross_border",
    "hour_utc", "input_reuse_share", "ip_entity_fanout", "ip_tx_count",
    "entity_n_addresses", "entity_n_txs", "entity_distinct_src_ips", "entity_distinct_src_countries",
    "entity_tor_share", "entity_countries_per_day", "entity_peel_chain_max",
)


def feature_matrix(graph: EntityGraph) -> pd.DataFrame:
    """Float feature matrix indexed by txid."""
    frame = graph.transactions.set_index("txid")[list(TX_FEATURES)]
    return frame.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
