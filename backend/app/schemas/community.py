"""Pydantic schemas for the /communities endpoint."""

from pydantic import BaseModel


class CommunityDetail(BaseModel):
    """Community members, size, and illicit ratio."""

    community_id: int
    size: int
    illicit_ratio: float | None
    mean_pagerank: float
    member_tx_ids: list[int]
