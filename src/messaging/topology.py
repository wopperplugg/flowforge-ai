from aio_pika import ExchangeType
from aio_pika.abc import AbstractRobustConnection

EVENTS_EXCHANGE = "flowforge.events"
AI_RETRY_EXCHANGE = "flowforge.ai.retry"
AI_DLX_EXCHANGE = "flowforge.ai.dlx"

AI_TASK_QUEUE = "flowforge.ai.tasks"
AI_TASK_ROUTING_KEY = "task.*"

AI_TASK_RETRY_10S_QUEUE = "flowforge.ai.tasks.retry.10s"
AI_TASK_RETRY_60S_QUEUE = "flowforge.ai.tasks.retry.60s"
AI_TASK_DLQ = "flowforge.ai.tasks.dlq"

AI_TASK_RETRY_10S_ROUTING_KEY = "flowforge.ai.tasks.retry.10s"
AI_TASK_RETRY_60S_ROUTING_KEY = "flowforge.ai.tasks.retry.60s"
AI_TASK_DLQ_ROUTING_KEY = "flowforge.ai.tasks.dlq"


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

        retry_exchange = await channel.declare_exchange(
            AI_RETRY_EXCHANGE,
            ExchangeType.DIRECT,
            durable=True,
        )

        dlx_exchange = await channel.declare_exchange(
            AI_DLX_EXCHANGE,
            ExchangeType.DIRECT,
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

        retry_10s_queue = await channel.declare_queue(
            AI_TASK_RETRY_10S_QUEUE,
            durable=True,
            arguments={
                "x-message-ttl": 10_000,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": AI_TASK_QUEUE,
            },
        )

        retry_60s_queue = await channel.declare_queue(
            AI_TASK_RETRY_60S_QUEUE,
            durable=True,
            arguments={
                "x-message-ttl": 60_000,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": AI_TASK_QUEUE,
            },
        )

        await retry_10s_queue.bind(
            retry_exchange,
            routing_key=AI_TASK_RETRY_10S_ROUTING_KEY,
        )

        await retry_60s_queue.bind(
            retry_exchange,
            routing_key=AI_TASK_RETRY_60S_ROUTING_KEY,
        )

        dlq = await channel.declare_queue(
            AI_TASK_DLQ,
            durable=True,
        )

        await dlq.bind(
            dlx_exchange,
            routing_key=AI_TASK_DLQ_ROUTING_KEY,
        )

    finally:
        await channel.close()
