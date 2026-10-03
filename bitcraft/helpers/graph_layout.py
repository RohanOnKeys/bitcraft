"""Layout types for the animated graph view.

A focus node, community or transaction hubs around it, and members around
each hub. bitcraft/widgets/graph_view.py builds these from the API's
subgraph and wallet link graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GraphNode:
    node_id: int
    cluster: int  # -1 = focus transaction
    kind: str  # "focus" | "hub" | "member"
    angle: float  # position inside its cluster (radians)
    radius: float  # 0..1 of the cluster radius
    risk: float


@dataclass
class GraphCluster:
    community_id: int
    angle: float  # position around the focus (radians)
    risk: float
    size: int
    label: str | None = None  # hub caption; defaults to C<community_id>


@dataclass
class GraphLayout:
    focus_tx: int
    clusters: list[GraphCluster]
    nodes: list[GraphNode]
    edges: list[tuple[int, int, str]] = field(default_factory=list)  # kind: hub|member|bridge
    focus_label: str | None = None  # caption for the focus node; defaults to "tx <id>"
