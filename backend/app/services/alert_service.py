"""Business logic for listing and retrieving alerts."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import redis_client
from app.models import Alert, AlertEvidence, Entity, Transaction, TxMetadata
from app.services.entity_service import tx_metadata_dict

MAX_PAGE = 500
SORTS = {
    "rank": (Alert.rank.asc(),),
    "anomaly": (Alert.anomaly_score.desc(), Alert.rank.asc()),
    "model": (Alert.model_score.desc(), Alert.rank.asc()),
    "community": (Alert.community_risk.desc(), Alert.rank.asc()),
    "network": (Alert.network_signal.desc(), Alert.rank.asc()),
}


@dataclass(frozen=True)
class AlertFilters:
    """Query-string filters for GET /alerts."""

    min_score: float | None = None
    community_id: int | None = None
    severities: tuple[str, ...] = ()
    network_required: bool = False
    synthetic_required: bool = False
    sort: str = "rank"


def _summary(alert: Alert, tx: Transaction) -> dict:
    return {
        "elliptic_tx_id": alert.elliptic_tx_id,
        "composite_score": alert.composite_score,
        "anomaly_score": alert.anomaly_score,
        "model_score": alert.model_score,
        "community_risk": alert.community_risk,
        "network_signal": alert.network_signal,
        "rank": alert.rank,
        "has_synthetic_layer": tx.has_synthetic_layer,
        "has_network_layer": tx.has_network_layer,
        "timestep": tx.timestep,
        "community_id": tx.community_id,
        "severity": alert.severity,
    }


def list_ranked_alerts(db: Session, filters: AlertFilters, offset: int, limit: int) -> dict:
    """Return a page of the ranked alert list, applying the given filters.

    Pages are cached in Redis (top-K list and hot filtered views) keyed by
    the full query, and invalidated by app/loader.py on reload.
    """
    limit = max(1, min(MAX_PAGE, limit))
    offset = max(0, offset)
    cache_key = f"alerts:{sorted(asdict(filters).items())}:{offset}:{limit}"
    cached = redis_client.cache_get(cache_key)
    if cached is not None:
        return cached

    query = select(Alert, Transaction).join(
        Transaction, Transaction.elliptic_tx_id == Alert.elliptic_tx_id
    )
    if filters.min_score is not None:
        query = query.where(Alert.composite_score >= filters.min_score)
    if filters.community_id is not None:
        query = query.where(Transaction.community_id == filters.community_id)
    if filters.severities:
        query = query.where(Alert.severity.in_(filters.severities))
    if filters.network_required:
        query = query.where(Transaction.has_network_layer.is_(True))
    if filters.synthetic_required:
        query = query.where(Transaction.has_synthetic_layer.is_(True))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = SORTS.get(filters.sort, SORTS["rank"])
    rows = db.execute(query.order_by(*order).offset(offset).limit(limit)).all()
    page = {
        "items": [_summary(alert, tx) for alert, tx in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
    redis_client.cache_set(cache_key, page)
    return page


def get_alert_detail(db: Session, tx_id: int) -> dict | None:
    """Return full alert detail for one transaction, including evidence."""
    row = db.execute(
        select(Alert, Transaction, AlertEvidence)
        .join(Transaction, Transaction.elliptic_tx_id == Alert.elliptic_tx_id)
        .outerjoin(AlertEvidence, AlertEvidence.elliptic_tx_id == Alert.elliptic_tx_id)
        .where(Alert.elliptic_tx_id == tx_id)
    ).first()
    if row is None:
        return None
    alert, tx, evidence = row
    detail = _summary(alert, tx)
    detail["evidence_text"] = evidence.evidence_text if evidence else ""
    detail["evidence_items"] = evidence.evidence_items if evidence else None
    detail["shap_reasons"] = evidence.shap_reasons if evidence else None
    meta = db.scalars(select(TxMetadata).where(TxMetadata.elliptic_tx_id == tx_id)).first()
    if meta is not None:
        detail["metadata"] = tx_metadata_dict(meta)
        wallet = db.get(Entity, meta.entity_id)
        if wallet is not None:
            detail["metadata"]["entity_rank"] = wallet.rank
            detail["metadata"]["entity_risk"] = wallet.risk_score
            detail["metadata"]["entity_addresses"] = wallet.n_addresses
    return detail
