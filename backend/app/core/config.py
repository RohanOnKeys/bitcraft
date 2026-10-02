"""Application settings loaded from environment variables.

With no DATABASE_URL the API uses a local SQLite file, so it runs with zero
setup; Docker Compose points it at PostgreSQL. Redis is optional: with no
REDIS_URL (or Redis down) caching is skipped and pipeline status is read
from the artifacts directory.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime configuration for the BitCraft API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'bitcraft.db').as_posix()}"
    redis_url: str | None = None
    artifacts_dir: Path = REPO_DIR / "ml" / "artifacts"
    cache_ttl_s: int = 300


settings = Settings()
