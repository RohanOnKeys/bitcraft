"""Wallets (entities), addresses, IPs and per-transaction metadata."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import redis_client
from app.models import Address, Entity, IpNode, TxIO, TxMetadata

MAX_PAGE = 500
DETAIL_ROWS = 50
GRAPH_TXS = 12
GRAPH_COUNTERPARTIES = 2

SUMMARY_FIELDS = (
    "entity_id", "rank", "risk_score", "severity", "n_addresses", "n_txs", "total_in_btc",
    "distinct_src_ips", "distinct_src_countries", "tor_share", "peel_chain_max", "linked_alerts",
)
DETAIL_FIELDS = SUMMARY_FIELDS + (
    "total_out_btc", "countries", "countries_per_day", "hosting_share", "round_output_share",
    "input_reuse_share", "first_seen", "last_seen", "evidence_text", "evidence_items", "shap_reasons",
)


def _fields(obj, names) -> dict:
    return {name: getattr(obj, name) for name in names}


def _columns(model) -> list[str]:
    return [c.name for c in model.__table__.columns if c.name != "id"]


def tx_metadata_dict(row: TxMetadata) -> dict:
    return _fields(row, _columns(TxMetadata))


def list_entities(db: Session, offset: int, limit: int, min_risk: float | None, sort: str) -> dict:
    """Ranked wallet alerts (one page)."""
    limit = max(1, min(MAX_PAGE, limit))
    key = f"entities:{offset}:{limit}:{min_risk}:{sort}"
    cached = redis_client.cache_get(key)
    if cached is not None:
        return cached
    query = select(Entity)
    if min_risk is not None:
        query = query.where(Entity.risk_score >= min_risk)
    order = {
        "rank": (Entity.rank.asc(),),
        "size": (Entity.n_addresses.desc(), Entity.rank.asc()),
        "countries": (Entity.distinct_src_countries.desc(), Entity.rank.asc()),
        "tor": (Entity.tor_share.desc(), Entity.rank.asc()),
    }.get(sort, (Entity.rank.asc(),))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(*order).offset(max(0, offset)).limit(limit)).all()
    page = {
        "items": [_fields(e, SUMMARY_FIELDS) for e in rows],
        "total": total,
        "offset": max(0, offset),
        "limit": limit,
    }
    redis_client.cache_set(key, page)
    return page


def _ip_rows(db: Session, ips) -> list[dict]:
    rows = db.scalars(select(IpNode).where(IpNode.ip.in_(list(ips)))).all()
    return [_fields(r, _columns(IpNode)) for r in rows]


def get_entity(db: Session, entity_id: int) -> dict | None:
    entity = db.get(Entity, entity_id)
    if entity is None:
        return None
    txs = db.scalars(
        select(TxMetadata)
        .where(TxMetadata.entity_id == entity_id)
        .order_by(TxMetadata.metadata_score.desc())
        .limit(DETAIL_ROWS)
    ).all()
    addresses = db.scalars(
        select(Address).where(Address.entity_id == entity_id).order_by(Address.n_tx_in.desc()).limit(DETAIL_ROWS)
    ).all()
    return {
        **_fields(entity, DETAIL_FIELDS),
        "addresses": [_fields(a, _columns(Address)) for a in addresses],
        "transactions": [tx_metadata_dict(t) for t in txs],
        "ips": _ip_rows(db, {t.src_ip for t in txs}),
    }


def get_address(db: Session, address: str) -> dict | None:
    row = db.get(Address, address)
    if row is None:
        return None
    txids = db.scalars(select(TxIO.txid).where(TxIO.address == address).distinct().limit(DETAIL_ROWS)).all()
    txs = db.scalars(select(TxMetadata).where(TxMetadata.txid.in_(txids)).order_by(TxMetadata.timestamp)).all()
    entity = db.get(Entity, row.entity_id)
    return {
        **_fields(row, _columns(Address)),
        "entity": _fields(entity, SUMMARY_FIELDS) if entity else None,
        "transactions": [tx_metadata_dict(t) for t in txs],
    }


def get_ip(db: Session, ip: str) -> dict | None:
    row = db.get(IpNode, ip)
    if row is None:
        return None
    txs = db.scalars(
        select(TxMetadata).where(TxMetadata.src_ip == ip).order_by(TxMetadata.timestamp).limit(DETAIL_ROWS)
    ).all()
    entity_ids = {t.entity_id for t in txs}
    entities = db.scalars(select(Entity).where(Entity.entity_id.in_(entity_ids)).order_by(Entity.rank)).all()
    return {
        **_fields(row, _columns(IpNode)),
        "transactions": [tx_metadata_dict(t) for t in txs],
        "entities": [_fields(e, SUMMARY_FIELDS) for e in entities],
    }


def get_tx_metadata(db: Session, elliptic_tx_id: int) -> dict | None:
    row = db.scalars(select(TxMetadata).where(TxMetadata.elliptic_tx_id == elliptic_tx_id)).first()
    return tx_metadata_dict(row) if row else None


def entity_graph(db: Session, entity_id: int) -> dict | None:
    """Wallet link graph: entity -> addresses -> txs <- ips, plus counterparties."""
    entity = db.get(Entity, entity_id)
    if entity is None:
        return None
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(node_id: str, kind: str, label: str, score: float | None = None) -> str:
        nodes.setdefault(node_id, {"id": node_id, "kind": kind, "label": label, "score": score})
        return node_id

    root = node(f"entity:{entity_id}", "entity", f"wallet {entity_id}", entity.risk_score)
    txs = db.scalars(
        select(TxMetadata)
        .where(TxMetadata.entity_id == entity_id)
        .order_by(TxMetadata.metadata_score.desc())
        .limit(GRAPH_TXS)
    ).all()
    txids = [t.txid for t in txs]
    io_rows = db.scalars(select(TxIO).where(TxIO.txid.in_(txids))).all()
    for t in txs:
        tx_node = node(f"tx:{t.txid}", "tx", t.txid[:10], t.metadata_score)
        ip_node = node(f"ip:{t.src_ip}", "ip", f"{t.src_ip} {t.src_country or ''}".strip())
        edges.append({"source": ip_node, "target": tx_node, "relation": "relayed"})
    counterparties: dict[str, int] = {}
    for io in io_rows:
        addr_node = f"addr:{io.address}"
        if io.direction == "in":
            node(addr_node, "address", io.address[:12])
            edges.append({"source": addr_node, "target": f"tx:{io.txid}", "relation": "input"})
            if {"source": root, "target": addr_node, "relation": "owns"} not in edges:
                edges.append({"source": root, "target": addr_node, "relation": "owns"})
        elif io.entity_id == entity_id or counterparties.get(io.txid, 0) < GRAPH_COUNTERPARTIES:
            if io.entity_id != entity_id:
                counterparties[io.txid] = counterparties.get(io.txid, 0) + 1
            node(addr_node, "address", io.address[:12])
            edges.append({"source": f"tx:{io.txid}", "target": addr_node, "relation": "output"})
    return {"nodes": list(nodes.values()), "edges": edges}
