import json
import uuid
from datetime import UTC, datetime

from src.agents.tools.flowforge import (
    create_flowforge_read_tools,
    create_flowforge_write_tools,
)
from src.flowforge_api.schemas import Page, TaskPriority, TaskResponse, TaskStatus


def make_task() -> TaskResponse:
    now = datetime.now(UTC)
    return TaskResponse(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        created_by_id=uuid.uuid4(),
        assigned_to_id=None,
        title="Task title",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        position=0,
        due_date=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


class FakeFlowForgeClient:
    def __init__(self) -> None:
        self.created = False

    async def get_project(self, project_id):
        now = datetime.now(UTC)
        return {
            "id": project_id,
            "organization_id": uuid.uuid4(),
            "name": "Project",
            "key": "PRJ",
            "description": None,
            "created_at": now,
            "updated_at": now,
        }

    async def list_tasks(self, project_id, *, limit=20, offset=0):
        return Page[TaskResponse](
            items=[make_task()],
            total=1,
            limit=limit,
            offset=offset,
        )

    async def get_task(self, task_id):
        return make_task()

    async def create_task(self, project_id, payload):
        self.created = True
        return make_task()

    async def update_task(self, task_id, payload):
        return make_task()


class FakeApprovalRepository:
    def __init__(self) -> None:
        self.calls = []

    async def create_approval(self, **kwargs):
        self.calls.append(kwargs)

        class Approval:
            id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        return Approval()


async def test_read_tool_lists_tasks() -> None:
    client = FakeFlowForgeClient()
    tools = create_flowforge_read_tools(client=client)
    list_tasks = next(item for item in tools if item.name == "list_tasks")

    result = await list_tasks.ainvoke(
        {
            "project_id": str(uuid.uuid4()),
            "limit": 5,
            "offset": 0,
        }
    )
    payload = json.loads(result)

    assert payload["total"] == 1
    assert payload["limit"] == 5
    assert payload["items"][0]["title"] == "Task title"


async def test_write_tool_requires_approval_before_http_mutation() -> None:
    client = FakeFlowForgeClient()
    tools = create_flowforge_write_tools(client=client, approved=False)
    create_task = next(item for item in tools if item.name == "create_task")

    result = await create_task.ainvoke(
        {
            "project_id": str(uuid.uuid4()),
            "title": "New task",
        }
    )
    payload = json.loads(result)

    assert payload["status"] == "approval_required"
    assert client.created is False


async def test_write_tool_persists_approval_request() -> None:
    client = FakeFlowForgeClient()
    approval_repository = FakeApprovalRepository()
    project_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tools = create_flowforge_write_tools(
        client=client,
        approved=False,
        approval_repository=approval_repository,
        thread_id="thread-1",
        organization_id=organization_id,
        project_context_id=project_id,
        user_id=user_id,
    )
    create_task = next(item for item in tools if item.name == "create_task")

    result = await create_task.ainvoke(
        {
            "project_id": str(project_id),
            "title": "New task",
        }
    )
    payload = json.loads(result)

    assert payload["status"] == "approval_required"
    assert payload["approval_id"] == "00000000-0000-0000-0000-000000000001"
    assert approval_repository.calls[0]["tool_name"] == "create_task"
    assert approval_repository.calls[0]["arguments"]["title"] == "New task"


async def test_write_tool_runs_when_approved() -> None:
    client = FakeFlowForgeClient()
    tools = create_flowforge_write_tools(client=client, approved=True)
    create_task = next(item for item in tools if item.name == "create_task")

    result = await create_task.ainvoke(
        {
            "project_id": str(uuid.uuid4()),
            "title": "New task",
        }
    )
    payload = json.loads(result)

    assert payload["title"] == "Task title"
    assert client.created is True
