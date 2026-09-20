"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the BitCraft API."""

    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql://bitcraft:bitcraft@localhost:5432/bitcraft"
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
