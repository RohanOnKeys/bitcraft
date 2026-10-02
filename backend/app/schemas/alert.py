"""Pydantic schemas for the /alerts endpoints."""

from pydantic import BaseModel


class AlertSummary(BaseModel):
    """One row in the paginated ranked alert list."""

    elliptic_tx_id: int
    composite_score: float
    anomaly_score: float
    model_score: float | None = None
    community_risk: float
    network_signal: float
    rank: int
    has_synthetic_layer: bool
    has_network_layer: bool
    timestep: int | None = None
    community_id: int | None = None
    severity: str | None = None


class AlertPage(BaseModel):
    """One page of ranked alerts plus the total matching count."""

    items: list[AlertSummary]
    total: int
    offset: int
    limit: int


class ShapReason(BaseModel):
    """One SHAP contribution; feature_index is -1 for engineered features."""

    feature: str
    feature_index: int
    contribution: float


class EvidenceItem(BaseModel):
    """One evidence field with its provenance (real or modeled)."""

    label: str
    value: str
    provenance: str


class AlertDetail(AlertSummary):
    """Full alert detail including SHAP and evidence."""

    shap_reasons: list[ShapReason] | None = None
    evidence_items: list[EvidenceItem] | None = None
    evidence_text: str
