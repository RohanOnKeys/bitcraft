"""Pydantic schemas for the /stats/summary endpoint."""

from pydantic import BaseModel


class StatsSummary(BaseModel):
    """Dashboard KPI summary."""

    total_transactions: int
    total_alerts: int
    labeled_coverage_pct: float
    network_coverage_pct: float
    full_stack_coverage_pct: float
