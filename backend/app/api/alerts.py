"""GET /alerts and GET /alerts/{tx_id}."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.alert import AlertDetail, AlertPage
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertPage)
def list_alerts(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=alert_service.MAX_PAGE),
    sort: str = Query("rank", pattern="^(rank|model|anomaly|community|network)$"),
    min_score: float | None = Query(None, ge=0, le=1),
    community_id: int | None = None,
    severity: str | None = Query(None, description="comma-separated tiers"),
    network_required: bool = False,
    synthetic_required: bool = False,
    db: Session = Depends(get_db),
):
    """Return the paginated, filterable ranked alert list."""
    severities = tuple(s.strip().lower() for s in (severity or "").split(",") if s.strip())
    filters = alert_service.AlertFilters(
        min_score=min_score,
        community_id=community_id,
        severities=severities,
        network_required=network_required,
        synthetic_required=synthetic_required,
        sort=sort,
    )
    return alert_service.list_ranked_alerts(db, filters, offset, limit)


@router.get("/{tx_id}", response_model=AlertDetail)
def get_alert(tx_id: int, db: Session = Depends(get_db)):
    """Return full alert detail: scores, SHAP, evidence, coverage flags."""
    detail = alert_service.get_alert_detail(db, tx_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"alert not found: {tx_id}")
    return detail
