"""ORM model for the alert_evidence table.

Populated by ml/explainability.py.
"""

from sqlalchemy import BigInteger, Column, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class AlertEvidence(Base):
    """SHAP reasons and human-readable evidence for one alert."""

    __tablename__ = "alert_evidence"

    elliptic_tx_id = Column(
        BigInteger, ForeignKey("alerts.elliptic_tx_id"), primary_key=True
    )
    shap_reasons = Column(JSONB, nullable=True)
    evidence_text = Column(Text, nullable=False)
