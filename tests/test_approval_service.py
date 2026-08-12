import uuid

from src.agents.approval_service import AssistantApprovalService


class FakeApproval:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.thread_id = "thread-1"
        self.organization_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.tool_name = "delete_task"
        self.arguments = {
            "project_id": str(self.project_id),
            "task_id": str(uuid.uuid4()),
        }
        self.status = "approved"
        self.result = None


class FakeRepository:
    def __init__(self, approval: FakeApproval) -> None:
        self.approval = approval
        self.messages = []

    async def get_approval_for_user(self, **kwargs):
        return self.approval

    async def set_approval_status(self, approval, status, *, result=None):
        approval.status = status
        approval.result = result
        return approval

    async def add_message(self, **kwargs):
        self.messages.append(kwargs)


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class FakeFlowForgeClient:
    def __init__(self) -> None:
        self.deleted = None

    async def delete_task(self, *, project_id, task_id) -> None:
        self.deleted = {
            "project_id": project_id,
            "task_id": task_id,
        }


async def test_approval_service_executes_approved_delete(monkeypatch) -> None:
    approval = FakeApproval()
    repository = FakeRepository(approval)
    session = FakeSession()
    client = FakeFlowForgeClient()
    service = AssistantApprovalService(
        session=session,
        flowforge_client=client,
    )
    monkeypatch.setattr(service, "_repository", repository)

    response = await service.execute(
        approval_id=approval.id,
        organization_id=approval.organization_id,
        user_id=approval.user_id,
    )

    assert response.approval.status == "executed"
    assert response.result["status"] == "deleted"
    assert client.deleted is not None
    assert session.committed is True
    assert repository.messages[0]["role"] == "tool"
