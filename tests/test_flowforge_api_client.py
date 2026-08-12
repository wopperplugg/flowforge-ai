import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest

from src.flowforge_api.client import FlowForgeAPIClient, FlowForgeAPIError
from src.flowforge_api.schemas import TaskCreate, TaskPriority, TaskStatus, TaskUpdate


def task_payload(
    *,
    task_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(task_id or uuid.uuid4()),
        "project_id": str(project_id or uuid.uuid4()),
        "created_by_id": str(uuid.uuid4()),
        "assigned_to_id": None,
        "title": "Task title",
        "description": "Task description",
        "status": TaskStatus.TODO.value,
        "priority": TaskPriority.MEDIUM.value,
        "position": 0,
        "due_date": None,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }


async def test_flowforge_api_client_forwards_bearer_and_lists_tasks(
    monkeypatch,
) -> None:
    project_id = uuid.uuid4()
    seen_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            json={
                "items": [task_payload(project_id=project_id)],
                "total": 1,
                "limit": 10,
                "offset": 5,
            },
        )

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    client = FlowForgeAPIClient(
        base_url="http://flowforge-api",
        access_token="access-token",
        timeout_seconds=3,
    )

    page = await client.list_tasks(project_id, limit=10, offset=5)

    assert seen_request is not None
    assert seen_request.url.path == f"/api/v1/projects/{project_id}/tasks"
    assert seen_request.url.params["limit"] == "10"
    assert seen_request.headers["authorization"] == "Bearer access-token"
    assert page.items[0].project_id == project_id


async def test_flowforge_api_client_maps_error_payload(
    monkeypatch,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": "Forbidden",
                }
            },
        )

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    client = FlowForgeAPIClient(
        base_url="http://flowforge-api",
        access_token="access-token",
        timeout_seconds=3,
    )

    with pytest.raises(FlowForgeAPIError) as exc_info:
        await client.get_task(uuid.uuid4())

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == "Forbidden"


async def test_flowforge_api_client_creates_and_updates_tasks(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []
    task_id = uuid.uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content),
            )
        )
        return httpx.Response(
            200 if request.method == "PATCH" else 201,
            json=task_payload(task_id=task_id),
        )

    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    client = FlowForgeAPIClient(
        base_url="http://flowforge-api",
        access_token="access-token",
        timeout_seconds=3,
    )

    created = await client.create_task(
        uuid.uuid4(),
        TaskCreate(title="New task"),
    )
    updated = await client.update_task(
        task_id,
        TaskUpdate(
            title="Updated task",
            version=1,
        ),
    )

    assert created.id == task_id
    assert updated.id == task_id
    assert calls[0][0] == "POST"
    assert calls[0][2]["title"] == "New task"
    assert calls[1][0] == "PATCH"
    assert calls[1][2]["title"] == "Updated task"
