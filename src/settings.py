from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="allow"
    )

    postgres_host: str = "localhost"
    postgres_database_name: str = "postgres"
    postgres_password: str = "postgres"
    postgres_port: int = 5432
    postgres_username: str = "postgres"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    kafka_bootstrap_servers: str = Field("localhost:9092", alias="KAFKA_BROKERS")
    kafka_topic_ads: str = Field("ads", alias="KAFKA_TOPIC_MARKETPLACE_ADS")
    auth_service_url: str = "http://localhost:8000"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_username}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_database_name}"
