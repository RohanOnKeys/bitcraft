"""ORM model for the alerts table.

Populated from ml/artifacts/alerts.parquet (ml/ranker.py).
"""

from sqlalchemy import BigInteger, Column, Float, ForeignKey, Integer, String

from app.core.database import Base


class Alert(Base):
    """Ranked alert for one transaction."""

    __tablename__ = "alerts"

    elliptic_tx_id = Column(
        BigInteger, ForeignKey("transactions.elliptic_tx_id"), primary_key=True
    )
    composite_score = Column(Float, nullable=False, index=True)
    anomaly_score = Column(Float, nullable=False)
    model_score = Column(Float, nullable=False, default=0.0)
    community_risk = Column(Float, nullable=False)
    network_signal = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)
