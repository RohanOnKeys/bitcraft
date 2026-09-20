"""Business logic for subgraph retrieval."""

from sqlalchemy.orm import Session


def get_subgraph(db: Session, tx_id: int, depth: int):
    """Return the subgraph around one transaction out to the given depth."""
    raise NotImplementedError
