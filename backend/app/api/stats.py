"""GET /stats/summary."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.stats import StatsSummary

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummary)
def get_stats_summary(db: Session = Depends(get_db)):
    """Return dashboard KPIs."""
    raise NotImplementedError
