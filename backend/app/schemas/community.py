"""Pydantic schemas for the /communities endpoints."""

from pydantic import BaseModel


class CommunitySummary(BaseModel):
    """Compact community row for overview lists."""

    community_id: int
    size: int
    illicit_ratio: float | None
    mean_pagerank: float
    alert_count: int = 0


class CommunityDetail(BaseModel):
    """Community members, size, and illicit ratio."""

    community_id: int
    size: int
    illicit_ratio: float | None
    mean_pagerank: float
    alert_count: int = 0
    member_tx_ids: list[int]
