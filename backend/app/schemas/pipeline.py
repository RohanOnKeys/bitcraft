"""Pydantic schemas for the /pipeline/status endpoint."""

from pydantic import BaseModel


class PipelineStatus(BaseModel):
    """Last/running ML pipeline job status, tracked through Redis."""

    status: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
