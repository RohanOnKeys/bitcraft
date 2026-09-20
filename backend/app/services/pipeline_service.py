"""Business logic for reading ML pipeline job status from Redis."""

from redis import Redis


def get_status(redis_client: Redis):
    """Return the last/running ML pipeline job status."""
    raise NotImplementedError
