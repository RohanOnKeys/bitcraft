"""ORM model for the alerts table.

Populated by ml/ranker.py.
"""

from sqlalchemy import BigInteger, Column, Float, ForeignKey, Integer

from app.core.database import Base


class Alert(Base):
    """Ranked alert for one transaction."""

    __tablename__ = "alerts"

    elliptic_tx_id = Column(
        BigInteger, ForeignKey("transactions.elliptic_tx_id"), primary_key=True
    )
    composite_score = Column(Float, nullable=False)
    anomaly_score = Column(Float, nullable=False)
    community_risk = Column(Float, nullable=False)
    network_signal = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False, index=True)
