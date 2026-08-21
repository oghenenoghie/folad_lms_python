from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Edge-service settings, shared shape with Django's env vars (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "sms"
    postgres_user: str = "sms"
    postgres_password: str = "sms"

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "insecure-dev-key-change-me"
    jwt_algorithm: str = "HS256"

    cors_allowed_origins: list[str] = []

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
