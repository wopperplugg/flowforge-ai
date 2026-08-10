from unittest.mock import AsyncMock, MagicMock

import pytest
from aio_pika import ExchangeType

from src.messaging import topology


@pytest.mark.asyncio
async def test_declare_ai_topology_declares_retry_and_dlq_topology() -> None:
    connection = MagicMock()
    connection.channel = AsyncMock()

    channel = MagicMock()
    channel.declare_exchange = AsyncMock()
    channel.declare_queue = AsyncMock()
    channel.close = AsyncMock()

    events_exchange = MagicMock()
    retry_exchange = MagicMock()
    dlx_exchange = MagicMock()
    main_queue = MagicMock()
    retry_10s_queue = MagicMock()
    retry_60s_queue = MagicMock()
    dlq = MagicMock()

    for queue in (
        main_queue,
        retry_10s_queue,
        retry_60s_queue,
        dlq,
    ):
        queue.bind = AsyncMock()

    connection.channel.return_value = channel
    channel.declare_exchange.side_effect = [
        events_exchange,
        retry_exchange,
        dlx_exchange,
    ]
    channel.declare_queue.side_effect = [
        main_queue,
        retry_10s_queue,
        retry_60s_queue,
        dlq,
    ]

    await topology.declare_ai_topology(connection)

    channel.declare_exchange.assert_any_await(
        topology.EVENTS_EXCHANGE,
        ExchangeType.TOPIC,
        durable=True,
    )
    channel.declare_exchange.assert_any_await(
        topology.AI_RETRY_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )
    channel.declare_exchange.assert_any_await(
        topology.AI_DLX_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )
    channel.declare_queue.assert_any_await(
        topology.AI_TASK_QUEUE,
        durable=True,
    )
    channel.declare_queue.assert_any_await(
        topology.AI_TASK_RETRY_10S_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 10_000,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": topology.AI_TASK_QUEUE,
        },
    )
    channel.declare_queue.assert_any_await(
        topology.AI_TASK_RETRY_60S_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": 60_000,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": topology.AI_TASK_QUEUE,
        },
    )
    channel.declare_queue.assert_any_await(topology.AI_TASK_DLQ, durable=True)
    main_queue.bind.assert_awaited_once_with(
        events_exchange,
        routing_key=topology.AI_TASK_ROUTING_KEY,
    )
    retry_10s_queue.bind.assert_awaited_once_with(
        retry_exchange,
        routing_key=topology.AI_TASK_RETRY_10S_ROUTING_KEY,
    )
    retry_60s_queue.bind.assert_awaited_once_with(
        retry_exchange,
        routing_key=topology.AI_TASK_RETRY_60S_ROUTING_KEY,
    )
    dlq.bind.assert_awaited_once_with(
        dlx_exchange,
        routing_key=topology.AI_TASK_DLQ_ROUTING_KEY,
    )
    channel.close.assert_awaited_once_with()
