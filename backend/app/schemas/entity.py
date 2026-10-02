"""Pydantic schemas for wallets (entities), addresses, IPs and tx metadata."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.alert import EvidenceItem


class ShapFeature(BaseModel):
    feature: str
    feature_index: int
    contribution: float


class EntitySummary(BaseModel):
    """One ranked wallet in the wallet alert list."""

    entity_id: int
    rank: int
    risk_score: float
    severity: str
    n_addresses: int
    n_txs: int
    total_in_btc: float
    distinct_src_ips: int
    distinct_src_countries: int
    tor_share: float
    peel_chain_max: int
    linked_alerts: int


class EntityPage(BaseModel):
    items: list[EntitySummary]
    total: int
    offset: int
    limit: int


class TxMetadataOut(BaseModel):
    """Correlated network + blockchain metadata for one transaction."""

    txid: str
    elliptic_tx_id: int | None = None
    entity_id: int
    timestamp: datetime
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    src_country: str | None = None
    src_asn: int | None = None
    src_asn_org: str | None = None
    dst_country: str | None = None
    dst_asn: int | None = None
    dst_asn_org: str | None = None
    script_type: str | None = None
    n_inputs: int
    n_outputs: int
    total_in_btc: float
    total_out_btc: float
    fee: float
    peel_like: bool
    peel_chain_len: int
    tor_port: bool
    src_tor_asn: bool
    src_hosting_asn: bool
    cross_border: bool
    metadata_score: float


class AddressOut(BaseModel):
    address: str
    entity_id: int
    script_type: str
    n_tx_in: int
    n_tx_out: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class IpOut(BaseModel):
    ip: str
    n_txs: int
    n_entities: int
    country: str | None = None
    asn: int | None = None
    asn_org: str | None = None
    tor_asn: bool
    hosting_asn: bool


class EntityDetail(EntitySummary):
    total_out_btc: float
    countries: list[str] | None = None
    countries_per_day: float | None = None
    hosting_share: float
    round_output_share: float
    input_reuse_share: float
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    evidence_text: str
    evidence_items: list[EvidenceItem] | None = None
    shap_reasons: list[ShapFeature] | None = None
    addresses: list[AddressOut]
    transactions: list[TxMetadataOut]
    ips: list[IpOut]


class AddressDetail(AddressOut):
    entity: EntitySummary | None = None
    transactions: list[TxMetadataOut]


class IpDetail(IpOut):
    transactions: list[TxMetadataOut]
    entities: list[EntitySummary]


class LinkNode(BaseModel):
    """Node in a wallet link graph: entity, address, tx or ip."""

    id: str
    kind: str
    label: str
    score: float | None = None


class LinkEdge(BaseModel):
    source: str
    target: str
    relation: str


class LinkGraph(BaseModel):
    nodes: list[LinkNode]
    edges: list[LinkEdge]
