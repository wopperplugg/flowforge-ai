from functools import lru_cache

from pydantic import Field, PostgresDsn, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "FlowForge AI"
    app_environment: str = "development"
    app_debug: bool = False

    postgres_host: str = Field(
        default="localhost",
        alias="POSTGRES_HOST",
    )
    postgres_port: int = Field(
        default=5434,
        alias="POSTGRES_PORT",
        ge=1,
        le=65535,
    )
    postgres_db: str = Field(
        default="flowforgeai",
        alias="POSTGRES_DB",
    )
    postgres_user: str = Field(
        default="flowforgeai",
        alias="POSTGRES_USER",
    )
    postgres_password: SecretStr = Field(
        default=SecretStr("flowforgeai"),
        alias="POSTGRES_PASSWORD",
    )

    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "qwen3:8b"

    @computed_field
    @property
    def postgres_dsn(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            path=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()