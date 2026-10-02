"""ORM model for the alert_evidence table.

Populated from ml/artifacts/evidence.parquet (ml/explainability.py).
"""

from sqlalchemy import BigInteger, Column, ForeignKey, Text

from app.core.database import Base, JsonType


class AlertEvidence(Base):
    """SHAP reasons and human-readable evidence for one alert."""

    __tablename__ = "alert_evidence"

    elliptic_tx_id = Column(
        BigInteger, ForeignKey("alerts.elliptic_tx_id"), primary_key=True
    )
    shap_reasons = Column(JsonType, nullable=True)
    evidence_items = Column(JsonType, nullable=True)
    evidence_text = Column(Text, nullable=False)
