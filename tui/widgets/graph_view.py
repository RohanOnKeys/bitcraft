"""Animated link-analysis view drawn on a braille canvas.

The focus transaction sits in the middle with a pulsing ripple; community
hubs orbit it slowly, each fanning out to its members. Bright packets run
along the edges so the graph reads as live flow. Stub data for now (see
tui/helpers/stub_charts.py); GET /graph/{tx_id} will replace it.
"""

from __future__ import annotations

import math

from rich.style import Style
from rich.text import Text
from textual.widget import Widget

from tui.helpers.stub_charts import StubCluster, StubNetwork, StubNode, stub_network
from tui.providers.models import ProviderError, Subgraph
from tui.widgets.charts import (
    CHROME,
    CRIMSON,
    MUTED,
    PINK,
    SERIES,
    TEXT,
    YELLOW,
    Canvas,
    dim,
    mix,
)

FPS = 12
# Most hubs / members drawn around one focus, so the view stays legible.
MAX_HUBS = 8
MAX_MEMBERS = 12


def network_from_subgraph(sub: Subgraph, focus_tx: int) -> StubNetwork:
    """Lay a real depth-2 subgraph out as focus -> hubs -> members.

    Hubs are the focus's direct neighbours (highest score first), members
    are each hub's own neighbours. Hub labels carry the neighbour's
    community and composite score.
    """
    score = {n.elliptic_tx_id: (n.composite_score or 0.0) for n in sub.nodes}
    community = {n.elliptic_tx_id: n.community_id for n in sub.nodes}
    adjacency: dict[int, list[tuple[int, str]]] = {}
    for e in sub.edges:
        adjacency.setdefault(e.source_tx_id, []).append((e.target_tx_id, e.data_source))
        adjacency.setdefault(e.target_tx_id, []).append((e.source_tx_id, e.data_source))

    hubs = sorted({n for n, _ in adjacency.get(focus_tx, [])}, key=lambda n: -score.get(n, 0.0))[:MAX_HUBS]
    clusters: list[StubCluster] = []
    nodes = [StubNode(0, -1, "focus", 0.0, 0.0, score.get(focus_tx, 0.0))]
    edges: list[tuple[int, int, str]] = []
    placed = {focus_tx: 0}
    for c, hub in enumerate(hubs):
        angle = 2 * math.pi * c / max(1, len(hubs))
        clusters.append(StubCluster(community.get(hub) or 0, angle, round(score.get(hub, 0.0), 2), 0))
        hub_node = StubNode(len(nodes), c, "hub", 0.0, 0.0, score.get(hub, 0.0))
        nodes.append(hub_node)
        placed[hub] = hub_node.node_id
        edges.append((0, hub_node.node_id, "hub"))
    for c, hub in enumerate(hubs):
        members = [n for n, _ in adjacency.get(hub, []) if n not in placed][:MAX_MEMBERS]
        clusters[c].size = len(members)
        for m, member in enumerate(members):
            node = StubNode(
                len(nodes), c, "member",
                2 * math.pi * m / max(1, len(members)), 0.6 + 0.4 * ((m * 7) % 5) / 4,
                score.get(member, 0.0),
            )
            nodes.append(node)
            placed[member] = node.node_id
            edges.append((placed[hub], node.node_id, "member"))
    # Edges between already-placed nodes that are not the tree above.
    tree = {(a, b) for a, b, _ in edges} | {(b, a) for a, b, _ in edges}
    for e in sub.edges:
        a, b = placed.get(e.source_tx_id), placed.get(e.target_tx_id)
        if a is not None and b is not None and (a, b) not in tree:
            edges.append((a, b, "bridge"))
            tree |= {(a, b), (b, a)}
    return StubNetwork(focus_tx, clusters, nodes, edges)
ROTATE_PER_FRAME = 0.0035
PACKET_FRAMES = 26


class GraphView(Widget):
    """Pan-free animated connectivity graph, coloured by community."""

    DEFAULT_CSS = """
    GraphView {
        width: 1fr;
        height: 1fr;
    }
    """

    def __init__(
        self,
        elliptic_tx_id: int | None = None,
        *,
        clusters: int = 5,
        labels: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.elliptic_tx_id = elliptic_tx_id
        self._labels = labels
        self._frame = 0
        self._net: StubNetwork = stub_network(
            focus_tx=elliptic_tx_id or 10000021,
            n_clusters=clusters,
            seed=(elliptic_tx_id or 7) % 97,
        )

    def on_mount(self) -> None:
        self.set_interval(1 / FPS, self._tick)
        if self.elliptic_tx_id is not None:
            self._load(self.elliptic_tx_id)

    def _load(self, tx_id: int) -> None:
        """Fetch the real subgraph off the UI thread; keep the layout on failure."""

        def work() -> None:
            try:
                sub = self.app.store.provider.subgraph(tx_id, depth=2)
            except (ProviderError, AttributeError):
                return
            if not sub.nodes:
                return
            net = network_from_subgraph(sub, tx_id)
            self.app.call_from_thread(self._apply, tx_id, net)

        self.run_worker(work, thread=True, exclusive=True, group="subgraph")

    def _apply(self, tx_id: int, net: StubNetwork) -> None:
        if tx_id == self.elliptic_tx_id:
            self._net = net
            self.refresh()

    def _tick(self) -> None:
        self._frame += 1
        self.refresh()

    def set_focus_tx(self, tx_id: int | None) -> None:
        """Rebuild the stub neighbourhood around a new transaction."""
        if tx_id == self.elliptic_tx_id:
            return
        self.elliptic_tx_id = tx_id
        self._net = stub_network(
            focus_tx=tx_id or 10000021,
            n_clusters=max(1, len(self._net.clusters)),
            seed=(tx_id or 7) % 97,
        )
        self.refresh()
        if tx_id is not None and self.is_mounted:
            self._load(tx_id)

    def _positions(self, canvas: Canvas) -> list[tuple[float, float]]:
        theta = self._frame * ROTATE_PER_FRAME
        cx, cy = canvas.w / 2, canvas.h / 2
        rx, ry = canvas.w * 0.34, canvas.h * 0.33
        local = min(rx, ry) * 0.62
        pos: list[tuple[float, float]] = []
        centres = [
            (cx + rx * math.cos(c.angle + theta), cy + ry * math.sin(c.angle + theta))
            for c in self._net.clusters
        ]
        for n in self._net.nodes:
            if n.kind == "focus":
                pos.append((cx, cy))
            elif n.kind == "hub":
                pos.append(centres[n.cluster])
            else:
                hx, hy = centres[n.cluster]
                a = n.angle - theta * 2.2
                pos.append((hx + local * n.radius * math.cos(a),
                            hy + local * n.radius * math.sin(a) * 0.9))
        return pos

    def render(self) -> Text:
        cols, rows = self.size.width, self.size.height
        if cols < 10 or rows < 5:
            return Text("")
        canvas = Canvas(cols, rows)
        pos = self._positions(canvas)
        net = self._net
        colour = lambda n: SERIES[n.cluster % len(SERIES)] if n.cluster >= 0 else YELLOW  # noqa: E731

        # Ripple rings around the focus.
        fx, fy = pos[0]
        for k in range(3):
            phase = ((self._frame / 18.0) + k / 3) % 1.0
            r = 3 + phase * min(canvas.w, canvas.h) * 0.16
            canvas.circle(fx, fy, r, mix(YELLOW, "#000000", 0.35 + phase * 0.6), prio=0)

        # Edges.
        for a, b, kind in net.edges:
            (x0, y0), (x1, y1) = pos[a], pos[b]
            na, nb = net.nodes[a], net.nodes[b]
            if kind == "bridge":
                canvas.line(x0, y0, x1, y1, dim(PINK, 0.45), prio=1, dash=2)
            elif kind == "hub":
                canvas.line(x0, y0, x1, y1, mix(YELLOW, colour(nb), 0.5), prio=2)
            else:
                canvas.line(x0, y0, x1, y1, dim(colour(na), 0.35), prio=1)

        # Packets: bright dots travelling along a rotating choice of edges.
        n_edges = len(net.edges)
        for k in range(10 if n_edges else 0):
            step = self._frame + k * 7
            edge = net.edges[(k * 13 + step // PACKET_FRAMES * 5) % n_edges]
            t = (step % PACKET_FRAMES) / PACKET_FRAMES
            (x0, y0), (x1, y1) = pos[edge[0]], pos[edge[1]]
            for trail in range(3):
                tt = max(0.0, t - trail * 0.04)
                canvas.dot(x0 + (x1 - x0) * tt, y0 + (y1 - y0) * tt,
                           mix("#fff6d8", CHROME, trail * 0.4), prio=5)

        # Node glyphs on top.
        for n, (x, y) in zip(net.nodes, pos):
            col, row = int(x) // 2, int(y) // 4
            if n.kind == "focus":
                pulse = (math.sin(self._frame / 3.0) + 1) / 2
                canvas.put(col, row, "◆", Style(color=mix(YELLOW, CRIMSON, pulse), bold=True))
                if self._labels:
                    canvas.put(col + 2, row, f"tx {net.focus_tx}",
                               Style(color=YELLOW, bold=True))
            elif n.kind == "hub":
                canvas.put(col, row, "◉", Style(color=colour(n), bold=True))
                if self._labels:
                    c = net.clusters[n.cluster]
                    canvas.put(col + 2, row, f"C{c.community_id}",
                               Style(color=colour(n), bold=True))
                    canvas.put(col + 2, row + 1, f"{c.risk:.2f}", Style(color=MUTED))
            else:
                glyph = "●" if n.risk >= 0.6 else "•"
                shade = colour(n) if n.risk >= 0.45 else dim(colour(n), 0.3)
                canvas.put(col, row, glyph, Style(color=shade))
        return canvas.to_text()


def graph_legend(net_clusters: int = 5) -> Text:
    """Legend line for the connectivity view."""
    text = Text(no_wrap=True, end="")
    text.append("◆ ", Style(color=YELLOW, bold=True))
    text.append("focus  ", Style(color=MUTED))
    text.append("◉ ", Style(color=TEXT))
    text.append("hub  ", Style(color=MUTED))
    text.append("● ", Style(color=TEXT))
    text.append("high-risk  ", Style(color=MUTED))
    text.append("• ", Style(color=MUTED))
    text.append("member  ", Style(color=MUTED))
    text.append("⠒⠒ ", Style(color=dim(PINK, 0.45)))
    text.append("bridge", Style(color=MUTED))
    return text
