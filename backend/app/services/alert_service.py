"""Business logic for listing and retrieving alerts."""

from sqlalchemy.orm import Session


def list_ranked_alerts(db: Session, filters: dict, page: int, page_size: int):
    """Return a page of the ranked alert list, applying the given filters."""
    raise NotImplementedError


def get_alert_detail(db: Session, tx_id: int):
    """Return full alert detail for one transaction, including evidence."""
    raise NotImplementedError
