"""GET /communities/{community_id}."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.community import CommunityDetail

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("/{community_id}", response_model=CommunityDetail)
def get_community(community_id: int, db: Session = Depends(get_db)):
    """Return community members, size, and illicit ratio."""
    raise NotImplementedError
