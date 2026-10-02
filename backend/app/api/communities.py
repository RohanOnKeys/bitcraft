"""GET /communities and GET /communities/{community_id}."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.community import CommunityDetail, CommunitySummary
from app.services import community_service

router = APIRouter(prefix="/communities", tags=["communities"])


@router.get("", response_model=list[CommunitySummary])
def list_communities(
    limit: int = Query(25, ge=1, le=200),
    sort: str = Query("risk", pattern="^(risk|alerts|size)$"),
    db: Session = Depends(get_db),
):
    """Return the highest-risk (or largest / most-alerted) communities."""
    return community_service.list_communities(db, limit, sort)


@router.get("/{community_id}", response_model=CommunityDetail)
def get_community(community_id: int, db: Session = Depends(get_db)):
    """Return community members, size, and illicit ratio."""
    detail = community_service.get_community_detail(db, community_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"community not found: {community_id}")
    return detail
