"""ORM model for the transactions table.

Populated from ml/artifacts/transactions.parquet (ml/pipeline.py) by
app/loader.py: one row per elliptic_tx_id with coverage flags, graph
features and fused scores.
"""

from sqlalchemy import BigInteger, Boolean, Column, Float, Integer, SmallInteger

from app.core.database import Base


class Transaction(Base):
    """One row per elliptic_tx_id in the master table."""

    __tablename__ = "transactions"

    elliptic_tx_id = Column(BigInteger, primary_key=True)
    timestep = Column(SmallInteger, nullable=False, index=True)
    class_label = Column(SmallInteger, nullable=True)
    has_synthetic_layer = Column(Boolean, nullable=False, default=False)
    has_network_layer = Column(Boolean, nullable=False, default=False)
    community_id = Column(Integer, nullable=True, index=True)
    degree = Column(Integer, nullable=True)
    pagerank = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)
    model_score = Column(Float, nullable=True)
    network_signal = Column(Float, nullable=True)
    composite_score = Column(Float, nullable=True)
