import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src.agents.rag.schemas import (
    AssistantQueryResponse,
    ProjectAssistantQueryResponse,
    ToolApprovalExecutionResponse,
    ToolApprovalResponse,
)
from src.agents.rag.service import AssistantTimeoutError
from src.api.dependencies import (
    get_assistant_approval_service,
    get_project_assistant_service,
    get_rag_assistant_service,
)
from src.api.main import create_app


class FakeAssistantService:
    def __init__(
        self,
        *,
        timeout: bool = False,
    ) -> None:
        self.timeout = timeout
        self.calls: list[dict[str, object]] = []

    async def query(self, **kwargs) -> AssistantQueryResponse:
        self.calls.append(kwargs)

        if self.timeout:
            raise AssistantTimeoutError("timeout")

        return AssistantQueryResponse(
            answer="Answer",
            thread_id=kwargs["thread_id"] or "generated-thread",
            query=kwargs["question"],
            rewrite_count=0,
            documents_relevant=True,
            sources=[],
        )


class FakeProjectAssistantService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def query(self, **kwargs) -> ProjectAssistantQueryResponse:
        self.calls.append(kwargs)
        return ProjectAssistantQueryResponse(
            answer="Agent answer",
            thread_id=kwargs["thread_id"] or "agent-thread",
            write_tools_enabled=bool(kwargs["allow_write_tools"]),
        )


class FakeApprovalService:
    async def approve(self, **kwargs) -> ToolApprovalResponse:
        return ToolApprovalResponse(
            id=kwargs["approval_id"],
            thread_id="thread-1",
            tool_name="create_task",
            arguments={"title": "Task"},
            status="approved",
        )

    async def reject(self, **kwargs) -> ToolApprovalResponse:
        return ToolApprovalResponse(
            id=kwargs["approval_id"],
            thread_id="thread-1",
            tool_name="create_task",
            arguments={"title": "Task"},
            status="rejected",
        )

    async def execute(self, **kwargs) -> ToolApprovalExecutionResponse:
        approval = ToolApprovalResponse(
            id=kwargs["approval_id"],
            thread_id="thread-1",
            tool_name="create_task",
            arguments={"title": "Task"},
            status="executed",
            result={"id": "task-1"},
        )
        return ToolApprovalExecutionResponse(
            approval=approval,
            result={"id": "task-1"},
        )


@pytest.fixture
def app():
    created_app = create_app()
    yield created_app
    created_app.dependency_overrides.clear()


async def test_query_assistant_requires_authenticated_context(app) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/assistant/query",
            json={
                "project_id": str(uuid.uuid4()),
                "question": "How does auth work?",
            },
        )

    assert response.status_code == 401


async def test_query_assistant_rejects_missing_bearer_token(app) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/assistant/query",
            headers={
                "X-User-Id": str(uuid.uuid4()),
                "X-Organization-Id": str(uuid.uuid4()),
            },
            json={
                "project_id": str(uuid.uuid4()),
                "question": "How does auth work?",
            },
        )

    assert response.status_code == 401


async def test_query_assistant_returns_service_response(app) -> None:
    service = FakeAssistantService()

    app.dependency_overrides[get_rag_assistant_service] = lambda: service

    user_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/assistant/query",
            headers={
                "Authorization": "Bearer access-token",
                "X-User-Id": str(user_id),
                "X-Organization-Id": str(organization_id),
            },
            json={
                "project_id": str(project_id),
                "question": "How does auth work?",
                "thread_id": "thread-1",
            },
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "Answer"
    assert service.calls == [
        {
            "organization_id": organization_id,
            "project_id": project_id,
            "user_id": user_id,
            "question": "How does auth work?",
            "thread_id": "thread-1",
        }
    ]


async def test_query_assistant_maps_timeout_to_504(app) -> None:
    app.dependency_overrides[get_rag_assistant_service] = lambda: FakeAssistantService(
        timeout=True,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/assistant/query",
            headers={
                "Authorization": "Bearer access-token",
                "X-User-Id": str(uuid.uuid4()),
                "X-Organization-Id": str(uuid.uuid4()),
            },
            json={
                "project_id": str(uuid.uuid4()),
                "question": "How does auth work?",
            },
        )

    assert response.status_code == 504


async def test_project_agent_endpoint_returns_service_response(app) -> None:
    service = FakeProjectAssistantService()

    app.dependency_overrides[get_project_assistant_service] = lambda: service

    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/assistant/agent/query",
            headers={
                "Authorization": "Bearer access-token",
                "X-User-Id": str(user_id),
                "X-Organization-Id": str(organization_id),
            },
            json={
                "project_id": str(project_id),
                "question": "List tasks",
                "thread_id": "agent-thread-1",
                "allow_write_tools": True,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Agent answer",
        "thread_id": "agent-thread-1",
        "write_tools_enabled": True,
    }
    assert service.calls == [
        {
            "organization_id": organization_id,
            "project_id": project_id,
            "user_id": user_id,
            "question": "List tasks",
            "thread_id": "agent-thread-1",
            "allow_write_tools": True,
        }
    ]


async def test_project_agent_stream_endpoint_returns_sse(app) -> None:
    app.dependency_overrides[get_project_assistant_service] = lambda: (
        FakeProjectAssistantService()
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/assistant/agent/stream",
            headers={
                "Authorization": "Bearer access-token",
                "X-User-Id": str(uuid.uuid4()),
                "X-Organization-Id": str(uuid.uuid4()),
            },
            json={
                "project_id": str(uuid.uuid4()),
                "question": "List tasks",
            },
        )

    assert response.status_code == 200
    assert "event: start" in response.text
    assert "event: final" in response.text
    assert "Agent answer" in response.text


async def test_approval_endpoints_use_authenticated_context(app) -> None:
    approval_id = uuid.uuid4()
    app.dependency_overrides[get_assistant_approval_service] = lambda: (
        FakeApprovalService()
    )

    headers = {
        "Authorization": "Bearer access-token",
        "X-User-Id": str(uuid.uuid4()),
        "X-Organization-Id": str(uuid.uuid4()),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        approve_response = await client.post(
            f"/v1/assistant/approvals/{approval_id}/approve",
            headers=headers,
        )
        execute_response = await client.post(
            f"/v1/assistant/approvals/{approval_id}/execute",
            headers=headers,
        )

    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"
    assert execute_response.status_code == 200
    assert execute_response.json()["approval"]["status"] == "executed"


async def test_health_returns_ok(app) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
