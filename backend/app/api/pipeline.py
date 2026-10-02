"""GET /pipeline/status and GET /pipeline/metrics."""

from fastapi import APIRouter, HTTPException

from app.schemas.pipeline import PipelineStatus
from app.services import pipeline_service

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/status", response_model=PipelineStatus)
def get_pipeline_status():
    """Return the last/running ML pipeline job status from Redis."""
    return pipeline_service.get_status()


@router.get("/metrics")
def get_pipeline_metrics() -> dict:
    """Return validation metrics (precision@k, modularity, coverage)."""
    metrics = pipeline_service.get_metrics()
    if metrics is None:
        raise HTTPException(status_code=404, detail="no pipeline metrics yet")
    return metrics
