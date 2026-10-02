"""Wallets, addresses, IPs and transaction metadata endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.entity import (
    AddressDetail,
    EntityDetail,
    EntityPage,
    IpDetail,
    LinkGraph,
    TxMetadataOut,
)
from app.services import entity_service

router = APIRouter(tags=["wallets"])


def _found(value, what: str):
    if value is None:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return value


@router.get("/entities", response_model=EntityPage)
def list_entities(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=entity_service.MAX_PAGE),
    min_risk: float | None = Query(None, ge=0, le=1),
    sort: str = Query("rank", pattern="^(rank|size|countries|tor)$"),
    db: Session = Depends(get_db),
):
    """Ranked wallet alerts (address clusters) with confidence scores."""
    return entity_service.list_entities(db, offset, limit, min_risk, sort)


@router.get("/entities/{entity_id}", response_model=EntityDetail)
def get_entity(entity_id: int, db: Session = Depends(get_db)):
    """One wallet: evidence, addresses, transactions and source IPs."""
    return _found(entity_service.get_entity(db, entity_id), f"wallet {entity_id}")


@router.get("/entities/{entity_id}/graph", response_model=LinkGraph)
def get_entity_graph(entity_id: int, db: Session = Depends(get_db)):
    """Link graph: wallet -> addresses -> transactions <- IPs."""
    return _found(entity_service.entity_graph(db, entity_id), f"wallet {entity_id}")


@router.get("/addresses/{address}", response_model=AddressDetail)
def get_address(address: str, db: Session = Depends(get_db)):
    """One address, its wallet and its transactions."""
    return _found(entity_service.get_address(db, address), f"address {address}")


@router.get("/ips/{ip}", response_model=IpDetail)
def get_ip(ip: str, db: Session = Depends(get_db)):
    """One source IP with GeoIP attribution, transactions and wallets."""
    return _found(entity_service.get_ip(db, ip), f"ip {ip}")


@router.get("/metadata/{tx_id}", response_model=TxMetadataOut)
def get_tx_metadata(tx_id: int, db: Session = Depends(get_db)):
    """Network + blockchain metadata linked to an Elliptic transaction."""
    return _found(entity_service.get_tx_metadata(db, tx_id), f"metadata for {tx_id}")
