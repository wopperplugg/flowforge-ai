import asyncio

from src.messaging.connection import create_rabbitmq_connection
from src.messaging.topology import declare_ai_topology


async def main() -> None:
    connection = await create_rabbitmq_connection()

    try:
        await declare_ai_topology(connection)
        print("RabbitMQ connection: OK")
        print("AI topology: OK")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())