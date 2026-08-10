from aio_pika import ExchangeType
from aio_pika.abc import AbstractRobustConnection

EVENTS_EXCHANGE = "flowforge.events"

AI_TASK_QUEUE = "flowforge.ai.tasks"
AI_TASK_ROUTING_KEY = "task.*"


async def declare_ai_topology(
    connection: AbstractRobustConnection,
) -> None:
    channel = await connection.channel()

    try:
        exchange = await channel.declare_exchange(
            EVENTS_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )

        queue = await channel.declare_queue(
            AI_TASK_QUEUE,
            durable=True,
        )

        await queue.bind(
            exchange,
            routing_key=AI_TASK_ROUTING_KEY,
        )

    finally:
        await channel.close()
