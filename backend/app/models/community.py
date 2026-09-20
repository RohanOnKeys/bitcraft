"""ORM model for the communities table.

Populated by ml/graph_builder.py.
"""

from sqlalchemy import Column, Float, Integer

from app.core.database import Base


class Community(Base):
    """Louvain community summary statistics."""

    __tablename__ = "communities"

    community_id = Column(Integer, primary_key=True)
    size = Column(Integer, nullable=False)
    illicit_ratio = Column(Float, nullable=True)
    mean_pagerank = Column(Float, nullable=False)
