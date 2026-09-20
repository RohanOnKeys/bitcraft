"""Pydantic schemas for the /alerts endpoints."""

from pydantic import BaseModel


class AlertSummary(BaseModel):
    """One row in the paginated ranked alert list."""

    elliptic_tx_id: int
    composite_score: float
    anomaly_score: float
    community_risk: float
    network_signal: float
    rank: int
    has_synthetic_layer: bool
    has_network_layer: bool


class AlertDetail(AlertSummary):
    """Full alert detail including SHAP and evidence."""

    shap_reasons: dict | None = None
    evidence_text: str
