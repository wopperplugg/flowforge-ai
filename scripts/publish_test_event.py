import asyncio
import json
import uuid
from datetime import UTC, datetime

from aio_pika import DeliveryMode, Message

from src.messaging.connection import create_rabbitmq_connection
from src.messaging.topology import EVENTS_EXCHANGE


async def main() -> None:
    connection = await create_rabbitmq_connection()
    channel = await connection.channel()

    exchange = await channel.get_exchange(
        EVENTS_EXCHANGE,
        ensure=True,
    )

    event_id = uuid.uuid4()
    task_id = uuid.uuid4()
    organization_id = uuid.uuid4()

    payload = {
        "event_id": str(event_id),
        "event_type": "task.updated",
        "event_version": 1,
        "aggregate_type": "task",
        "aggregate_id": str(task_id),
        "correlation_id": str(event_id),
        "causation_id": None,
        "organization_id": str(organization_id),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {
            "title": "Тестовая задача",
            "description": "Проверка realtime события для AI",
        },
    }

    message = Message(
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
    )

    await exchange.publish(
        message,
        routing_key="task.updated",
    )

    print(f"Event published: {event_id}")

    await channel.close()
    await connection.close()


if __name__ == "__main__":
    asyncio.run(main())