"""GET /graph/{tx_id}."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.graph import Subgraph
from app.services import graph_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/{tx_id}", response_model=Subgraph)
def get_subgraph(
    tx_id: int,
    depth: int = Query(1, ge=1, le=graph_service.MAX_DEPTH),
    db: Session = Depends(get_db),
):
    """Return the subgraph around one transaction out to the given depth."""
    subgraph = graph_service.get_subgraph(db, tx_id, depth)
    if subgraph is None:
        raise HTTPException(status_code=404, detail=f"transaction not found: {tx_id}")
    return subgraph
