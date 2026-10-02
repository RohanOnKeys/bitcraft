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
