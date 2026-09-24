"""Deterministic demo data provider for offline TUI demos.

Seeded with random.Random(42). Numbers match plans/plan.md coverage
facts. Composite score weights mirrored from ml/config.yaml.
"""

from __future__ import annotations

import random
import time
from typing import Optional

from tui.helpers.severity import severity_for_score
from tui.providers.models import (
    AlertDetail,
    AlertPage,
    AlertQuery,
    AlertSummary,
    CommunityDetail,
    CommunitySummary,
    EvidenceItem,
    GraphEdge,
    GraphNode,
    Health,
    PipelineStatus,
    ProviderError,
    ShapReason,
    StatsSummary,
    Subgraph,
    ThreatOverview,
)

# Mirrored from ml/config.yaml (plans/plan.md section 7).
ANOMALY_WEIGHT = 0.60
COMMUNITY_WEIGHT = 0.25
NETWORK_WEIGHT = 0.15

TOTAL_TRANSACTIONS = 203_769
LABELED_COVERAGE_PCT = 22.9
SYNTHETIC_COVERAGE_PCT = 24.5
NETWORK_COVERAGE_PCT = 12.0
FULL_STACK_COVERAGE_PCT = 12.0
CONTAMINATION = 0.022
ALERT_COUNT = int(round(TOTAL_TRANSACTIONS * CONTAMINATION))  # 4483

_LATENCY_MIN_MS = 30
_LATENCY_MAX_MS = 120


class DemoProvider:
    """Fully deterministic synthetic provider. Never claims to be live data."""

    def __init__(self, seed: int = 42, simulate_latency: bool = False) -> None:
        self._seed = seed
        self._simulate_latency = simulate_latency
        self._rng = random.Random(seed)
        self._alerts: list[AlertSummary] = []
        self._communities: list[CommunitySummary] = []
        self._members: dict[int, list[int]] = {}
        self._build()

    @property
    def source_label(self) -> str:
        """Header badge label."""
        return "DEMO DATA"

    def _sleep(self) -> None:
        """Seeded artificial latency so loading states are exercised."""
        if not self._simulate_latency:
            return
        ms = self._rng.randint(_LATENCY_MIN_MS, _LATENCY_MAX_MS)
        time.sleep(ms / 1000.0)

    def _build(self) -> None:
        """Generate communities and ranked alerts once."""
        self._build_communities()
        self._build_alerts()

    def _build_communities(self) -> None:
        """Power-law community sizes; illicit_ratio None when unlabeled."""
        rng = random.Random(self._seed + 1)
        communities: list[CommunitySummary] = []
        members: dict[int, list[int]] = {}
        next_tx = 1_000_000
        for cid in range(40):
            size = max(5, int(5000 / ((cid + 1) ** 1.4)) + rng.randint(0, 20))
            unlabeled = rng.random() < 0.15
            if unlabeled:
                illicit: Optional[float] = None
            else:
                illicit = min(0.95, max(0.0, rng.betavariate(2, 8) + (0.3 if cid < 5 else 0.0)))
            mean_pr = rng.uniform(0.0001, 0.02)
            tx_ids = list(range(next_tx, next_tx + size))
            next_tx += size
            members[cid] = tx_ids
            communities.append(
                CommunitySummary(
                    community_id=cid,
                    size=size,
                    illicit_ratio=illicit,
                    mean_pagerank=mean_pr,
                    alert_count=0,
                )
            )
        self._communities = communities
        self._members = members

    def _build_alerts(self) -> None:
        """Heavy-tailed scores; ranked strictly by composite descending."""
        rng = random.Random(self._seed + 2)
        rows: list[AlertSummary] = []
        community_alert_counts = {c.community_id: 0 for c in self._communities}

        for i in range(ALERT_COUNT):
            # Heavy tail: small critical head, long low tail.
            u = (i + 1) / ALERT_COUNT
            anomaly = max(0.0, min(1.0, (1.0 - u) ** 0.25 + rng.gauss(0, 0.02)))
            community = rng.choice(self._communities)
            if community.illicit_ratio is None:
                community_risk = rng.uniform(0.0, 0.15)
            else:
                community_risk = max(
                    0.0,
                    min(1.0, community.illicit_ratio + rng.gauss(0, 0.05)),
                )
            # Guarantee a critical head for display tiers (>= 0.80 composite).
            if i < 120:
                anomaly = max(anomaly, 0.98)
                community_risk = max(community_risk, 0.85)
            has_network = rng.random() < (NETWORK_COVERAGE_PCT / 100.0)
            has_synthetic = has_network or (
                rng.random() < (SYNTHETIC_COVERAGE_PCT / 100.0)
            )
            if has_network:
                network_signal = max(0.0, min(1.0, rng.betavariate(2, 5)))
            else:
                network_signal = 0.0
            composite = (
                ANOMALY_WEIGHT * anomaly
                + COMMUNITY_WEIGHT * community_risk
                + NETWORK_WEIGHT * network_signal
            )
            tx_id = 10_000_000 + i
            severity = severity_for_score(composite)
            rows.append(
                AlertSummary(
                    elliptic_tx_id=tx_id,
                    composite_score=composite,
                    anomaly_score=anomaly,
                    community_risk=community_risk,
                    network_signal=network_signal,
                    rank=0,
                    has_synthetic_layer=has_synthetic,
                    has_network_layer=has_network,
                    timestep=rng.randint(1, 49),
                    community_id=community.community_id,
                    severity=severity,
                )
            )
            community_alert_counts[community.community_id] += 1

        rows.sort(key=lambda r: r.composite_score, reverse=True)
        ranked: list[AlertSummary] = []
        for rank, row in enumerate(rows, start=1):
            ranked.append(
                AlertSummary(
                    elliptic_tx_id=row.elliptic_tx_id,
                    composite_score=row.composite_score,
                    anomaly_score=row.anomaly_score,
                    community_risk=row.community_risk,
                    network_signal=row.network_signal,
                    rank=rank,
                    has_synthetic_layer=row.has_synthetic_layer,
                    has_network_layer=row.has_network_layer,
                    timestep=row.timestep,
                    community_id=row.community_id,
                    severity=row.severity,
                )
            )
        self._alerts = ranked
        self._communities = [
            CommunitySummary(
                community_id=c.community_id,
                size=c.size,
                illicit_ratio=c.illicit_ratio,
                mean_pagerank=c.mean_pagerank,
                alert_count=community_alert_counts[c.community_id],
            )
            for c in self._communities
        ]
        self._by_tx = {a.elliptic_tx_id: a for a in self._alerts}

    def health(self) -> Health:
        """Always healthy in demo mode."""
        self._sleep()
        return Health(status="ok")

    def stats_summary(self) -> StatsSummary:
        """Plan-aligned coverage KPIs."""
        self._sleep()
        return StatsSummary(
            total_transactions=TOTAL_TRANSACTIONS,
            total_alerts=ALERT_COUNT,
            labeled_coverage_pct=LABELED_COVERAGE_PCT,
            network_coverage_pct=NETWORK_COVERAGE_PCT,
            full_stack_coverage_pct=FULL_STACK_COVERAGE_PCT,
        )

    def pipeline_status(self) -> PipelineStatus:
        """Demo pipeline is always complete."""
        self._sleep()
        return PipelineStatus(
            status="complete",
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:02:00Z",
            error=None,
        )

    def _filtered(self, query: AlertQuery) -> list[AlertSummary]:
        """Apply alert query filters and sort."""
        rows = self._alerts
        if query.min_score is not None:
            rows = [r for r in rows if r.composite_score >= query.min_score]
        if query.community_id is not None:
            rows = [r for r in rows if r.community_id == query.community_id]
        if query.severities:
            allowed = set(query.severities)
            rows = [r for r in rows if r.severity in allowed]
        if query.network_required:
            rows = [r for r in rows if r.has_network_layer]
        if query.synthetic_required:
            rows = [r for r in rows if r.has_synthetic_layer]

        sort_key = {
            "rank": lambda r: r.rank,
            "anomaly": lambda r: -r.anomaly_score,
            "community": lambda r: -r.community_risk,
            "network": lambda r: -r.network_signal,
        }.get(query.sort, lambda r: r.rank)
        return sorted(rows, key=sort_key)

    def alerts(self, query: AlertQuery) -> AlertPage:
        """Paginated filtered alert list."""
        self._sleep()
        rows = self._filtered(query)
        page = rows[query.offset : query.offset + query.limit]
        return AlertPage(
            items=page, total=len(rows), offset=query.offset, limit=query.limit
        )

    def alert_detail(self, tx_id: int) -> AlertDetail:
        """Full detail with evidence and SHAP for one alert."""
        self._sleep()
        row = self._by_tx.get(tx_id)
        if row is None:
            raise ProviderError(f"alert not found: {tx_id}")

        community = next(
            (c for c in self._communities if c.community_id == row.community_id),
            None,
        )
        evidence_items: list[EvidenceItem] = []
        if community is not None:
            evidence_items.append(
                EvidenceItem(
                    label="community size",
                    value=str(community.size),
                    provenance="real",
                )
            )
            if community.illicit_ratio is not None:
                evidence_items.append(
                    EvidenceItem(
                        label="community illicit ratio",
                        value=f"{community.illicit_ratio:.2f}",
                        provenance="real",
                    )
                )
            else:
                evidence_items.append(
                    EvidenceItem(
                        label="community illicit ratio",
                        value="unlabeled",
                        provenance="real",
                    )
                )
        evidence_items.append(
            EvidenceItem(
                label="degree percentile",
                value=f"{min(99, int(row.anomaly_score * 100))}",
                provenance="real",
            )
        )
        if row.has_network_layer:
            evidence_items.append(
                EvidenceItem(
                    label="distinct country count",
                    value="3",
                    provenance="modeled",
                )
            )
            evidence_items.append(
                EvidenceItem(
                    label="distinct IP count",
                    value="5",
                    provenance="modeled",
                )
            )

        ratio_txt = (
            f"{community.illicit_ratio:.2f}"
            if community and community.illicit_ratio is not None
            else "unlabeled"
        )
        evidence_text = (
            f"Rank {row.rank} alert in community {row.community_id} "
            f"(illicit ratio {ratio_txt}). "
            f"Anomaly {row.anomaly_score:.2f}, community risk "
            f"{row.community_risk:.2f}, network "
            f"{'n/a' if not row.has_network_layer else f'~{row.network_signal:.2f}'}."
        )

        shap = [
            ShapReason(feature_index=idx, contribution=contrib)
            for idx, contrib in (
                (12, 0.18),
                (47, -0.11),
                (3, 0.09),
                (101, 0.07),
                (88, -0.05),
            )
        ]
        return AlertDetail(
            elliptic_tx_id=row.elliptic_tx_id,
            composite_score=row.composite_score,
            anomaly_score=row.anomaly_score,
            community_risk=row.community_risk,
            network_signal=row.network_signal,
            rank=row.rank,
            has_synthetic_layer=row.has_synthetic_layer,
            has_network_layer=row.has_network_layer,
            evidence_text=evidence_text,
            shap_reasons=shap,
            timestep=row.timestep,
            community_id=row.community_id,
            severity=row.severity,
            evidence_items=evidence_items,
        )

    def subgraph(self, tx_id: int, depth: int = 1) -> Subgraph:
        """Deterministic ego graph with real and modeled edges."""
        self._sleep()
        depth = max(1, min(3, depth))
        rng = random.Random(self._seed + tx_id)
        nodes = [GraphNode(elliptic_tx_id=tx_id, composite_score=None, community_id=0)]
        edges: list[GraphEdge] = []
        frontier = [tx_id]
        seen = {tx_id}
        for _ in range(depth):
            nxt: list[int] = []
            for src in frontier:
                for _n in range(rng.randint(2, 4)):
                    neighbor = src + rng.randint(1, 50) * (1 if rng.random() > 0.5 else -1)
                    if neighbor in seen or neighbor <= 0:
                        neighbor = src + len(seen) + 1
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    nxt.append(neighbor)
                    is_modeled = rng.random() < 0.4
                    nodes.append(
                        GraphNode(
                            elliptic_tx_id=neighbor,
                            composite_score=rng.random(),
                            community_id=rng.randint(0, 5),
                        )
                    )
                    edges.append(
                        GraphEdge(
                            source_tx_id=src,
                            target_tx_id=neighbor,
                            relationship_type=(
                                "same_timestep" if is_modeled else "elliptic_edge"
                            ),
                            data_source="synthetic" if is_modeled else "elliptic",
                        )
                    )
            frontier = nxt
            if not frontier:
                break
        return Subgraph(nodes=nodes, edges=edges)

    def community(self, community_id: int) -> CommunityDetail:
        """One community with member ids."""
        self._sleep()
        summary = next(
            (c for c in self._communities if c.community_id == community_id), None
        )
        if summary is None:
            raise ProviderError(f"community not found: {community_id}")
        return CommunityDetail(
            community_id=summary.community_id,
            size=summary.size,
            illicit_ratio=summary.illicit_ratio,
            mean_pagerank=summary.mean_pagerank,
            member_tx_ids=list(self._members.get(community_id, [])),
        )

    def top_communities(self, limit: int = 25) -> list[CommunitySummary]:
        """Communities sorted by illicit ratio then size."""
        self._sleep()

        def sort_key(c: CommunitySummary) -> tuple:
            ratio = c.illicit_ratio if c.illicit_ratio is not None else -1.0
            return (-ratio, -c.size)

        return sorted(self._communities, key=sort_key)[:limit]

    def threat_overview(self) -> ThreatOverview:
        """Severity and coverage aggregates across all alerts."""
        self._sleep()
        crit = high = med = low = no_net = 0
        per_ts: dict[int, int] = {}
        for row in self._alerts:
            if row.severity == "critical":
                crit += 1
            elif row.severity == "high":
                high += 1
            elif row.severity == "medium":
                med += 1
            else:
                low += 1
            if not row.has_network_layer:
                no_net += 1
            if row.timestep is not None:
                per_ts[row.timestep] = per_ts.get(row.timestep, 0) + 1
        high_illicit = sum(
            1
            for c in self._communities
            if c.illicit_ratio is not None and c.illicit_ratio >= 0.4
        )
        return ThreatOverview(
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low,
            no_network_evidence_count=no_net,
            high_illicit_community_count=high_illicit,
            alerts_per_timestep=per_ts,
        )
