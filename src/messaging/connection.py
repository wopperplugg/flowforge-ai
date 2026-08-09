import aio_pika

from aio_pika.abc import AbstractRobustConnection

from src.config import settings


async def create_rabbitmq_connection() -> AbstractRobustConnection:
    return await aio_pika.connect_robust(
        settings.rabbitmq_dsn.unicode_string(),
        client_properties={
            "connection_name": "flowforge-ai",
        },
    )