"""Business logic for subgraph retrieval."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import GraphEdge, Transaction

MAX_DEPTH = 3
# Hubs can have thousands of neighbours; cap the response so a terminal
# view stays readable and the query stays fast.
MAX_NODES = 150


def get_subgraph(db: Session, tx_id: int, depth: int) -> dict | None:
    """Return the subgraph around one transaction out to the given depth.

    Breadth-first over graph_edges in both directions, stopping once
    MAX_NODES nodes are collected. None when the transaction is unknown.
    """
    if db.get(Transaction, tx_id) is None:
        return None
    depth = max(1, min(MAX_DEPTH, depth))
    seen = {tx_id}
    frontier = [tx_id]
    edges: dict[tuple[int, int, str], GraphEdge] = {}
    for _ in range(depth):
        if not frontier or len(seen) >= MAX_NODES:
            break
        rows = db.scalars(
            select(GraphEdge).where(
                or_(GraphEdge.source_tx_id.in_(frontier), GraphEdge.target_tx_id.in_(frontier))
            )
        ).all()
        nxt: list[int] = []
        for edge in rows:
            for node in (edge.source_tx_id, edge.target_tx_id):
                if node not in seen and len(seen) < MAX_NODES:
                    seen.add(node)
                    nxt.append(node)
            if edge.source_tx_id in seen and edge.target_tx_id in seen:
                edges[(edge.source_tx_id, edge.target_tx_id, edge.relationship_type)] = edge
        frontier = nxt

    nodes = db.scalars(select(Transaction).where(Transaction.elliptic_tx_id.in_(seen))).all()
    by_id = {n.elliptic_tx_id: n for n in nodes}
    return {
        "nodes": [
            {
                "elliptic_tx_id": node_id,
                "composite_score": by_id[node_id].composite_score if node_id in by_id else None,
                "community_id": by_id[node_id].community_id if node_id in by_id else None,
            }
            for node_id in sorted(seen, key=lambda n: (n != tx_id, n))
        ],
        "edges": [
            {
                "source_tx_id": e.source_tx_id,
                "target_tx_id": e.target_tx_id,
                "relationship_type": e.relationship_type,
                "data_source": e.data_source,
            }
            for e in edges.values()
        ],
    }
