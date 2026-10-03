"""GET /stats/summary and GET /threats/overview."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.stats import StatsCharts, StatsSummary, ThreatOverview
from app.services import stats_service

router = APIRouter(tags=["stats"])


@router.get("/stats/summary", response_model=StatsSummary)
def get_stats_summary(db: Session = Depends(get_db)):
    """Return dashboard KPIs."""
    return stats_service.get_summary(db)


@router.get("/stats/charts", response_model=StatsCharts)
def get_stats_charts(db: Session = Depends(get_db)):
    """Return per-timestep series, degree histogram, BTC flow and the
    suspicious-traffic country x timestep matrix."""
    return stats_service.get_charts(db)


@router.get("/threats/overview", response_model=ThreatOverview)
def get_threat_overview(db: Session = Depends(get_db)):
    """Return severity mix, coverage gaps and per-timestep alert volume."""
    return stats_service.get_threat_overview(db)
