"""Business logic for dashboard KPI and threat aggregation."""

from __future__ import annotations

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core import redis_client
from app.models import Alert, Community, Transaction

HIGH_ILLICIT_RATIO = 0.4


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def get_summary(db: Session) -> dict:
    """Aggregate dashboard KPIs from the transactions and alerts tables."""
    cached = redis_client.cache_get("stats:summary")
    if cached is not None:
        return cached
    total, labeled, network, full = db.execute(
        select(
            func.count(),
            func.sum(case((Transaction.class_label.is_not(None), 1), else_=0)),
            func.sum(case((Transaction.has_network_layer.is_(True), 1), else_=0)),
            func.sum(
                case(
                    (and_(Transaction.has_network_layer.is_(True), Transaction.has_synthetic_layer.is_(True)), 1),
                    else_=0,
                )
            ),
        )
    ).one()
    alerts = db.scalar(select(func.count()).select_from(Alert)) or 0
    summary = {
        "total_transactions": int(total or 0),
        "total_alerts": int(alerts),
        "labeled_coverage_pct": _pct(int(labeled or 0), int(total or 0)),
        "network_coverage_pct": _pct(int(network or 0), int(total or 0)),
        "full_stack_coverage_pct": _pct(int(full or 0), int(total or 0)),
    }
    redis_client.cache_set("stats:summary", summary)
    return summary


def get_threat_overview(db: Session) -> dict:
    """Severity mix, coverage gaps and per-timestep volume across alerts."""
    cached = redis_client.cache_get("threats:overview")
    if cached is not None:
        return cached
    tiers = dict(db.execute(select(Alert.severity, func.count()).group_by(Alert.severity)).all())
    no_network = db.scalar(
        select(func.count())
        .select_from(Alert)
        .join(Transaction, Transaction.elliptic_tx_id == Alert.elliptic_tx_id)
        .where(Transaction.has_network_layer.is_(False))
    ) or 0
    high_illicit = db.scalar(
        select(func.count()).select_from(Community).where(Community.illicit_ratio >= HIGH_ILLICIT_RATIO)
    ) or 0
    per_ts = db.execute(
        select(Transaction.timestep, func.count())
        .join(Alert, Alert.elliptic_tx_id == Transaction.elliptic_tx_id)
        .group_by(Transaction.timestep)
        .order_by(Transaction.timestep)
    ).all()
    overview = {
        "critical_count": int(tiers.get("critical", 0)),
        "high_count": int(tiers.get("high", 0)),
        "medium_count": int(tiers.get("medium", 0)),
        "low_count": int(tiers.get("low", 0)),
        "no_network_evidence_count": int(no_network),
        "high_illicit_community_count": int(high_illicit),
        "alerts_per_timestep": {int(ts): int(n) for ts, n in per_ts},
    }
    redis_client.cache_set("threats:overview", overview)
    return overview
