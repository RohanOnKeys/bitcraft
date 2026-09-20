"""Business logic for community lookups."""

from sqlalchemy.orm import Session


def get_community_detail(db: Session, community_id: int):
    """Return members, size, and illicit ratio for one community."""
    raise NotImplementedError
