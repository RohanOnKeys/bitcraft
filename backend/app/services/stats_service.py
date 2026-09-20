"""Business logic for dashboard KPI aggregation."""

from sqlalchemy.orm import Session


def get_summary(db: Session):
    """Aggregate dashboard KPIs from the transactions and alerts tables."""
    raise NotImplementedError
