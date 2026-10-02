"""Deterministic stub data for the chart panels.

Stand-in series for the graph explorer and chart panels until the backend
exposes them. Seeded so every run (and every recording) looks the same.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class StubNode:
    node_id: int
    cluster: int  # -1 = focus transaction
    kind: str  # "focus" | "hub" | "member"
    angle: float  # position inside its cluster (radians)
    radius: float  # 0..1 of the cluster radius
    risk: float


@dataclass
class StubCluster:
    community_id: int
    angle: float  # position around the focus (radians)
    risk: float
    size: int


@dataclass
class StubNetwork:
    focus_tx: int
    clusters: list[StubCluster]
    nodes: list[StubNode]
    edges: list[tuple[int, int, str]] = field(default_factory=list)  # kind: hub|member|bridge


def stub_network(focus_tx: int = 10000021, n_clusters: int = 5, seed: int = 7) -> StubNetwork:
    """Focus tx wired to community hubs, each hub fanning out to members."""
    rng = random.Random(seed)
    clusters: list[StubCluster] = []
    nodes = [StubNode(0, -1, "focus", 0.0, 0.0, 0.87)]
    edges: list[tuple[int, int, str]] = []
    ids = [0, 7, 15, 22, 23, 4, 2, 27]
    for c in range(n_clusters):
        angle = 2 * math.pi * c / n_clusters + rng.uniform(-0.25, 0.25)
        risk = round(rng.uniform(0.35, 0.95), 2)
        size = rng.randint(7, 13)
        clusters.append(StubCluster(ids[c % len(ids)], angle, risk, size))
        hub = StubNode(len(nodes), c, "hub", 0.0, 0.0, risk)
        nodes.append(hub)
        edges.append((0, hub.node_id, "hub"))
        members = []
        for m in range(size):
            a = 2 * math.pi * m / size + rng.uniform(-0.2, 0.2)
            node = StubNode(len(nodes), c, "member", a, rng.uniform(0.55, 1.0),
                            max(0.05, min(1.0, risk + rng.uniform(-0.35, 0.2))))
            nodes.append(node)
            members.append(node.node_id)
            edges.append((hub.node_id, node.node_id, "member"))
        for _ in range(size // 3):
            a, b = rng.sample(members, 2)
            edges.append((a, b, "member"))
    hubs = [n.node_id for n in nodes if n.kind == "hub"]
    for i in range(len(hubs)):
        edges.append((hubs[i], hubs[(i + 1) % len(hubs)], "bridge"))
    members_all = [n for n in nodes if n.kind == "member"]
    for _ in range(4):
        a, b = rng.sample(members_all, 2)
        if a.cluster != b.cluster:
            edges.append((a.node_id, b.node_id, "bridge"))
    return StubNetwork(focus_tx, clusters, nodes, edges)


def alerts_by_timestep(seed: int = 3) -> list[float]:
    """49 Elliptic timesteps of alert volume with a dark-market spike."""
    rng = random.Random(seed)
    out = []
    for t in range(1, 50):
        base = 40 + 25 * math.sin(t / 4.0) + 10 * math.sin(t / 1.7)
        spike = 95 * math.exp(-((t - 26) ** 2) / 8.0) + 50 * math.exp(-((t - 41) ** 2) / 5.0)
        out.append(max(4.0, base + spike + rng.uniform(-8, 8)))
    return out


def activity_heatmap(rows: int = 14, cols: int = 24, seed: int = 11) -> list[list[float]]:
    """Weekday x hour activity, busiest in the late-evening UTC window."""
    rng = random.Random(seed)
    matrix = []
    for r in range(rows):
        row = []
        for c in range(cols):
            v = 0.25 + 0.6 * math.exp(-((c - 20) ** 2) / 18) + 0.35 * math.exp(-((c - 3) ** 2) / 6)
            v *= 1.0 + 0.4 * math.sin(r / 2.0)
            row.append(max(0.0, v + rng.uniform(-0.12, 0.12)))
        matrix.append(row)
    return matrix


def community_risk_bars() -> list[tuple[str, float, int]]:
    """(label, illicit ratio, size) for the top communities."""
    return [
        ("C0", 0.66, 5001), ("C7", 0.59, 286), ("C15", 0.49, 105),
        ("C22", 0.47, 79), ("C23", 0.39, 66), ("C4", 0.39, 541),
        ("C2", 0.38, 1086), ("C27", 0.37, 67),
    ]


def degree_distribution() -> list[float]:
    """Heavy-tailed node degree histogram (log-ish buckets)."""
    return [820, 610, 402, 288, 190, 131, 88, 61, 40, 27, 18, 12, 8, 5, 3, 2]


def score_mix() -> list[tuple[str, float]]:
    """Share of alerts by severity tier."""
    return [("critical", 121), ("high", 612), ("medium", 1480), ("low", 2270)]


def driver_mix() -> list[tuple[str, float]]:
    """Share of the composite score by driver across critical/high alerts."""
    return [("anomaly", 0.599), ("community", 0.213), ("network", 0.061)]


def flow_series(seed: int = 5) -> tuple[list[float], list[float]]:
    """Inbound vs outbound BTC flow for the focus neighbourhood (stub)."""
    rng = random.Random(seed)
    inbound = [max(0.5, 6 + 4 * math.sin(i / 3) + rng.uniform(-1.5, 1.5)) for i in range(32)]
    outbound = [max(0.5, 5 + 4 * math.cos(i / 3.4) + rng.uniform(-1.5, 1.5)) for i in range(32)]
    return inbound, outbound
