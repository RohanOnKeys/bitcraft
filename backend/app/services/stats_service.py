"""Business logic for dashboard KPI and threat aggregation."""

from __future__ import annotations

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core import redis_client
from app.models import Alert, Community, Transaction, TxMetadata
from app.services import pipeline_service

HIGH_ILLICIT_RATIO = 0.4
# Metadata-model score at which a transaction counts as suspicious traffic.
SUSPICIOUS_SCORE = 0.5
# Countries shown in the suspicious-traffic matrix, busiest first.
TOP_COUNTRIES = 8
# Degree histogram: exact degrees 1..DEGREE_CAP-1, then one open bucket.
DEGREE_CAP = 16


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


def _per_timestep(rows, timesteps: list[int], cast=int) -> list:
    """Align (timestep, value) rows to the full timestep list, zero filled."""
    values = {int(ts): value for ts, value in rows if ts is not None}
    return [cast(values.get(ts) or 0) for ts in timesteps]


def get_charts(db: Session) -> dict:
    """Series for the dashboard sparklines and the graph explorer charts.

    Everything is aggregated from the loaded tables: transactions, alerts,
    tx_metadata, plus the stage timings in the pipeline metrics.
    """
    cached = redis_client.cache_get("stats:charts")
    if cached is not None:
        return cached
    ts_col = Transaction.timestep
    per_ts = db.execute(
        select(
            ts_col,
            func.count(),
            func.sum(case((Transaction.class_label.is_not(None), 1), else_=0)),
            func.sum(case((Transaction.has_network_layer.is_(True), 1), else_=0)),
        ).group_by(ts_col).order_by(ts_col)
    ).all()
    timesteps = [int(row[0]) for row in per_ts if row[0] is not None]
    alert_rows = db.execute(
        select(
            ts_col,
            func.count(),
            func.sum(case((Alert.severity == "critical", 1), else_=0)),
        )
        .join(Alert, Alert.elliptic_tx_id == Transaction.elliptic_tx_id)
        .group_by(ts_col)
    ).all()

    degrees = db.execute(select(Transaction.degree, func.count()).group_by(Transaction.degree)).all()
    counts = [0] * DEGREE_CAP
    for degree, n in degrees:
        if degree is not None and degree >= 1:
            counts[min(int(degree), DEGREE_CAP) - 1] += int(n)
    buckets = [str(d) for d in range(1, DEGREE_CAP)] + [f"{DEGREE_CAP}+"]

    meta_ts = (
        select(ts_col, TxMetadata.total_in_btc, TxMetadata.src_country, TxMetadata.metadata_score,
               Alert.elliptic_tx_id.label("alert_id"))
        .select_from(TxMetadata)
        .join(Transaction, Transaction.elliptic_tx_id == TxMetadata.elliptic_tx_id)
        .outerjoin(Alert, Alert.elliptic_tx_id == TxMetadata.elliptic_tx_id)
        .subquery()
    )
    flow = db.execute(
        select(
            meta_ts.c.timestep,
            func.sum(meta_ts.c.total_in_btc),
            func.sum(case((meta_ts.c.alert_id.is_not(None), meta_ts.c.total_in_btc), else_=0.0)),
        ).group_by(meta_ts.c.timestep)
    ).all()
    suspicious = db.execute(
        select(meta_ts.c.src_country, meta_ts.c.timestep, func.count())
        .where(meta_ts.c.metadata_score >= SUSPICIOUS_SCORE, meta_ts.c.src_country.is_not(None))
        .group_by(meta_ts.c.src_country, meta_ts.c.timestep)
    ).all()
    by_country: dict[str, dict[int, int]] = {}
    for country, ts, n in suspicious:
        by_country.setdefault(str(country), {})[int(ts)] = int(n)
    top = sorted(by_country, key=lambda c: -sum(by_country[c].values()))[:TOP_COUNTRIES]

    metrics = pipeline_service.get_metrics() or {}
    charts = {
        "timesteps": timesteps,
        "transactions": _per_timestep([(r[0], r[1]) for r in per_ts], timesteps),
        "alerts": _per_timestep([(r[0], r[1]) for r in alert_rows], timesteps),
        "critical": _per_timestep([(r[0], r[2]) for r in alert_rows], timesteps),
        "labeled": _per_timestep([(r[0], r[2]) for r in per_ts], timesteps),
        "network": _per_timestep([(r[0], r[3]) for r in per_ts], timesteps),
        "stage_seconds": {k: float(v) for k, v in (metrics.get("timings_s") or {}).items()},
        "degree_buckets": buckets,
        "degree_counts": counts,
        "flow_all_btc": _per_timestep([(r[0], r[1]) for r in flow], timesteps, float) if flow else [],
        "flow_alerted_btc": _per_timestep([(r[0], r[2]) for r in flow], timesteps, float) if flow else [],
        "country_rows": top,
        "country_matrix": [[by_country[c].get(ts, 0) for ts in timesteps] for c in top],
    }
    redis_client.cache_set("stats:charts", charts)
    return charts
