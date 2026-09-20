"""GET /pipeline/status."""

from fastapi import APIRouter

from app.schemas.pipeline import PipelineStatus

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/status", response_model=PipelineStatus)
def get_pipeline_status():
    """Return the last/running ML pipeline job status from Redis."""
    raise NotImplementedError
