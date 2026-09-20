"""GET /graph/{tx_id}."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.graph import Subgraph

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/{tx_id}", response_model=Subgraph)
def get_subgraph(tx_id: int, depth: int = 1, db: Session = Depends(get_db)):
    """Return the subgraph around one transaction out to the given depth."""
    raise NotImplementedError
