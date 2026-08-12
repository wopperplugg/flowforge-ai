import uuid

from langchain_core.messages import AIMessage, SystemMessage

from src.agents.project_service import ProjectAssistantService


class FakeEmbeddingProvider:
    model_name = "test-embedding"

    async def embed_text(self, query: str) -> list[float]:
        return [0.1, 0.2]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class FakeFlowForgeClient:
    pass


class FakeAgent:
    def __init__(self) -> None:
        self.config = None
        self.input = None

    async def ainvoke(self, input, config=None):
        self.config = config
        self.input = input
        return {
            "messages": [
                AIMessage(content="Agent answer"),
            ]
        }


class FakeConversationRepository:
    def __init__(self) -> None:
        self.messages = []

    async def ensure_thread(self, **kwargs):
        self.thread = kwargs

    async def list_messages(self, **kwargs):
        return []

    async def add_message(self, **kwargs):
        self.messages.append(kwargs)


async def test_project_assistant_service_returns_last_agent_message() -> None:
    agent = FakeAgent()
    conversation_repository = FakeConversationRepository()
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    service = ProjectAssistantService(
        session=object(),
        embedding_provider=FakeEmbeddingProvider(),
        flowforge_client=FakeFlowForgeClient(),
        timeout_seconds=1,
        recursion_limit=9,
        agent=agent,
        conversation_repository=conversation_repository,
    )

    response = await service.query(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user_id,
        question="List tasks",
        thread_id="thread-1",
        allow_write_tools=True,
    )

    assert response.answer == "Agent answer"
    assert response.thread_id == "thread-1"
    assert response.write_tools_enabled is True
    assert agent.config == {
        "recursion_limit": 9,
        "configurable": {
            "thread_id": "thread-1",
        },
    }
    system_message = agent.input["messages"][0]
    assert isinstance(system_message, SystemMessage)
    assert str(project_id) in system_message.content
    assert str(organization_id) in system_message.content
    assert [message["role"] for message in conversation_repository.messages] == [
        "user",
        "assistant",
    ]
