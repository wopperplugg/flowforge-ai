from functools import lru_cache

from pydantic import AmqpDsn, Field, PostgresDsn, SecretStr, computed_field
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

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = Field(default=5672, ge=1, le=65535)
    rabbitmq_user: str = "guest"
    rabbitmq_password: SecretStr = SecretStr("guest")
    rabbitmq_vhost: str = "/"    

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

    @computed_field
    @property
    def rabbitmq_dsn(self) -> AmqpDsn:
        return AmqpDsn.build(
            scheme="amqp",
            username=self.rabbitmq_user,
            password=self.rabbitmq_password.get_secret_value(),
            host=self.rabbitmq_host,
            port=self.rabbitmq_port,
            path=self.rabbitmq_vhost,
        )    

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()