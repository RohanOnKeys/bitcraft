"""Business logic for community lookups."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Community, Transaction

MAX_MEMBERS = 500


def _summary(c: Community) -> dict:
    return {
        "community_id": c.community_id,
        "size": c.size,
        "illicit_ratio": c.illicit_ratio,
        "mean_pagerank": c.mean_pagerank,
        "alert_count": c.alert_count,
    }


def get_community_detail(db: Session, community_id: int) -> dict | None:
    """Return members, size, and illicit ratio for one community.

    Members are capped at MAX_MEMBERS, highest composite score first.
    """
    community = db.get(Community, community_id)
    if community is None:
        return None
    members = db.scalars(
        select(Transaction.elliptic_tx_id)
        .where(Transaction.community_id == community_id)
        .order_by(Transaction.composite_score.desc())
        .limit(MAX_MEMBERS)
    ).all()
    return {**_summary(community), "member_tx_ids": list(members)}


def list_communities(db: Session, limit: int, sort: str = "risk") -> list[dict]:
    """Top communities: by illicit ratio (unlabeled last), alerts, or size."""
    limit = max(1, min(200, limit))
    order = {
        "risk": (Community.illicit_ratio.is_(None), Community.illicit_ratio.desc(), Community.size.desc()),
        "alerts": (Community.alert_count.desc(), Community.size.desc()),
        "size": (Community.size.desc(),),
    }.get(sort)
    if order is None:
        order = (Community.illicit_ratio.is_(None), Community.illicit_ratio.desc())
    # Tiny communities make noisy ratios; keep the overview to real clusters.
    rows = db.scalars(select(Community).where(Community.size >= 5).order_by(*order).limit(limit)).all()
    return [_summary(c) for c in rows]
