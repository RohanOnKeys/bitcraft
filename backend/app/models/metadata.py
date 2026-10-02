"""ORM models for the metadata layer: wallets, addresses, IPs, tx metadata.

Populated from ml/artifacts/{entities,addresses,ips,tx_metadata,tx_io}.parquet
(ml/metadata_model.py, ml/entity_graph.py) by app/loader.py.
"""

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, Integer, String, Text

from app.core.database import Base, JsonType


class Entity(Base):
    """A wallet: addresses clustered by common-input ownership."""

    __tablename__ = "entities"

    entity_id = Column(Integer, primary_key=True)
    rank = Column(Integer, nullable=False, index=True)
    risk_score = Column(Float, nullable=False, index=True)
    severity = Column(String(16), nullable=False)
    n_addresses = Column(Integer, nullable=False)
    n_txs = Column(Integer, nullable=False)
    total_in_btc = Column(Float, nullable=False)
    total_out_btc = Column(Float, nullable=False)
    distinct_src_ips = Column(Integer, nullable=False)
    distinct_src_countries = Column(Integer, nullable=False)
    countries = Column(JsonType, nullable=True)
    countries_per_day = Column(Float, nullable=True)
    tor_share = Column(Float, nullable=False)
    hosting_share = Column(Float, nullable=False)
    peel_chain_max = Column(Integer, nullable=False)
    round_output_share = Column(Float, nullable=False)
    input_reuse_share = Column(Float, nullable=False)
    linked_alerts = Column(Integer, nullable=False, default=0)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    top_txid = Column(String(64), nullable=True)
    evidence_text = Column(Text, nullable=False, default="")
    evidence_items = Column(JsonType, nullable=True)
    shap_reasons = Column(JsonType, nullable=True)


class Address(Base):
    """One wallet address and the entity it belongs to."""

    __tablename__ = "addresses"

    address = Column(String(100), primary_key=True)
    entity_id = Column(Integer, nullable=False, index=True)
    script_type = Column(String(16), nullable=False)
    n_tx_in = Column(Integer, nullable=False)
    n_tx_out = Column(Integer, nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)


class IpNode(Base):
    """A source IP seen relaying transactions, with its GeoIP attribution."""

    __tablename__ = "ip_nodes"

    ip = Column(String(45), primary_key=True)
    n_txs = Column(Integer, nullable=False)
    n_entities = Column(Integer, nullable=False)
    country = Column(String(8), nullable=True)
    asn = Column(BigInteger, nullable=True)
    asn_org = Column(String(200), nullable=True)
    tor_asn = Column(Boolean, nullable=False, default=False)
    hosting_asn = Column(Boolean, nullable=False, default=False)


class TxMetadata(Base):
    """Network + blockchain metadata for one transaction (txid)."""

    __tablename__ = "tx_metadata"

    txid = Column(String(64), primary_key=True)
    elliptic_tx_id = Column(BigInteger, nullable=True, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    src_ip = Column(String(45), nullable=False, index=True)
    src_port = Column(Integer, nullable=False)
    dst_ip = Column(String(45), nullable=False)
    dst_port = Column(Integer, nullable=False)
    src_country = Column(String(8), nullable=True)
    src_asn = Column(BigInteger, nullable=True)
    src_asn_org = Column(String(200), nullable=True)
    dst_country = Column(String(8), nullable=True)
    dst_asn = Column(BigInteger, nullable=True)
    dst_asn_org = Column(String(200), nullable=True)
    script_type = Column(String(16), nullable=True)
    n_inputs = Column(Integer, nullable=False)
    n_outputs = Column(Integer, nullable=False)
    total_in_btc = Column(Float, nullable=False)
    total_out_btc = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    peel_like = Column(Boolean, nullable=False)
    peel_chain_len = Column(Integer, nullable=False)
    tor_port = Column(Boolean, nullable=False)
    src_tor_asn = Column(Boolean, nullable=False)
    src_hosting_asn = Column(Boolean, nullable=False)
    cross_border = Column(Boolean, nullable=False)
    metadata_score = Column(Float, nullable=False)


class TxIO(Base):
    """One input or output of a transaction."""

    __tablename__ = "tx_io"

    id = Column(Integer, primary_key=True, autoincrement=True)
    txid = Column(String(64), nullable=False, index=True)
    address = Column(String(100), nullable=False, index=True)
    direction = Column(String(3), nullable=False)
    amount = Column(Float, nullable=False)
    position = Column(Integer, nullable=False)
    entity_id = Column(Integer, nullable=False, index=True)
