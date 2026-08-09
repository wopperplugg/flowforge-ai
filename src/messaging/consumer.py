import json

from aio_pika import IncomingMessage
from pydantic import ValidationError

from src.messaging.contracts import OutboxMessage


async def handle_task_event(message: IncomingMessage) -> None:
    try:
        payload = json.loads(message.body)
        event = OutboxMessage.model_validate(payload)

        print(
            "received event:",
            event.event_type,
            event.aggregate_id,
        )
        await message.ack()
        
    except (json.JSONDecodeError, ValidationError) as exc:
        print("invalid message:", exc)

        await message.reject(requeue=False)

    except Exception:
        await message.reject(requeue=True)
        raise