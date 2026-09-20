"""Pydantic schemas for the /graph endpoint."""

from pydantic import BaseModel


class GraphNode(BaseModel):
    """One transaction node in a subgraph response."""

    elliptic_tx_id: int
    composite_score: float | None = None
    community_id: int | None = None


class GraphEdgeSchema(BaseModel):
    """One relationship edge in a subgraph response."""

    source_tx_id: int
    target_tx_id: int
    relationship_type: str
    data_source: str


class Subgraph(BaseModel):
    """Subgraph around one transaction, out to the requested depth."""

    nodes: list[GraphNode]
    edges: list[GraphEdgeSchema]
