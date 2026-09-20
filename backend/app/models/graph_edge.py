"""ORM model for the graph_edges table.

Populated by ml/graph_builder.py.
"""

from sqlalchemy import BigInteger, Column, Integer, String

from app.core.database import Base


class GraphEdge(Base):
    """One transaction-to-transaction relationship edge."""

    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_tx_id = Column(BigInteger, nullable=False, index=True)
    target_tx_id = Column(BigInteger, nullable=False, index=True)
    relationship_type = Column(String, nullable=False)
    data_source = Column(String, nullable=False)
