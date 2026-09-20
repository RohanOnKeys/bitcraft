"""ORM model for the transactions table.

Populated by ml/data_loader.py.
"""

from sqlalchemy import BigInteger, Boolean, Column, SmallInteger

from app.core.database import Base


class Transaction(Base):
    """One row per elliptic_tx_id in the master table."""

    __tablename__ = "transactions"

    elliptic_tx_id = Column(BigInteger, primary_key=True)
    timestep = Column(SmallInteger, nullable=False)
    class_label = Column(SmallInteger, nullable=True)
    has_synthetic_layer = Column(Boolean, nullable=False, default=False)
    has_network_layer = Column(Boolean, nullable=False, default=False)
