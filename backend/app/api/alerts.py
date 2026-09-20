"""GET /alerts and GET /alerts/{tx_id}."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.alert import AlertDetail, AlertSummary

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertSummary])
def list_alerts(db: Session = Depends(get_db)):
    """Return the paginated, filterable ranked alert list."""
    raise NotImplementedError


@router.get("/{tx_id}", response_model=AlertDetail)
def get_alert(tx_id: int, db: Session = Depends(get_db)):
    """Return full alert detail: scores, SHAP, evidence, coverage flags."""
    raise NotImplementedError
