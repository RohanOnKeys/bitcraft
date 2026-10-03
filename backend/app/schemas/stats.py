"""Pydantic schemas for the /stats and /threats endpoints."""

from pydantic import BaseModel


class StatsSummary(BaseModel):
    """Dashboard KPI summary."""

    total_transactions: int
    total_alerts: int
    labeled_coverage_pct: float
    network_coverage_pct: float
    full_stack_coverage_pct: float


class ThreatOverview(BaseModel):
    """Severity, coverage and timeline aggregates for the threats screen."""

    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    no_network_evidence_count: int
    high_illicit_community_count: int
    alerts_per_timestep: dict[int, int]


class StatsCharts(BaseModel):
    """Series behind the dashboard sparklines and graph explorer charts.

    Per-timestep lists align with `timesteps`. The metadata-layer fields
    are empty when no metadata was loaded.
    """

    timesteps: list[int]
    transactions: list[int]
    alerts: list[int]
    critical: list[int]
    labeled: list[int]
    network: list[int]
    stage_seconds: dict[str, float]
    degree_buckets: list[str]
    degree_counts: list[int]
    flow_all_btc: list[float]
    flow_alerted_btc: list[float]
    country_rows: list[str]
    country_matrix: list[list[int]]
