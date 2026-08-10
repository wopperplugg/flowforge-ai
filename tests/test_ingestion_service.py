import uuid
from unittest.mock import AsyncMock

import pytest

from src.ingestion.chunker import TextChunk, TextChunker
from src.ingestion.schemas import IndexSourceCommand
from src.ingestion.service import IngestionService
from src.knowledge.models import KnowledgeSource


class FakeEmbeddingProvider:
    model_name = "test-embedding"

    def __init__(
        self,
        embeddings: list[list[float]],
    ) -> None:
        self.embeddings = embeddings
        self.embed_documents = AsyncMock(return_value=embeddings)


class FakeChunker:
    def __init__(
        self,
        chunks: list[TextChunk],
    ) -> None:
        self.chunks = chunks

    def split(
        self,
        text: str,
    ) -> list[TextChunk]:
        return self.chunks


class FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()


class FakeRepository:
    def __init__(
        self,
        session: object,
        existing_source: KnowledgeSource | None = None,
    ) -> None:
        self.session = session
        self.existing_source = existing_source
        self.add_source = AsyncMock(side_effect=self._add_source)
        self.add_chunks = AsyncMock()
        self.delete_chunks = AsyncMock()
        self.get_source = AsyncMock(return_value=existing_source)

    async def _add_source(
        self,
        source: KnowledgeSource,
    ) -> KnowledgeSource:
        source.id = uuid.uuid4()
        return source


def make_command(
    *,
    content: str = "Hello   world",
    source_entity_id: uuid.UUID | None = None,
) -> IndexSourceCommand:
    return IndexSourceCommand(
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        source_type="task",
        source_entity_id=source_entity_id,
        title="Task title",
        content=content,
        metadata={"source": "test"},
    )


@pytest.mark.asyncio
async def test_index_source_creates_source_and_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    repository = FakeRepository(session)

    monkeypatch.setattr(
        "src.ingestion.service.KnowledgeRepository",
        lambda session: repository,
    )

    service = IngestionService(
        session=session,  # type: ignore[arg-type]
        embedding_provider=FakeEmbeddingProvider([[0.1, 0.2]]),  # type: ignore[arg-type]
        chunker=FakeChunker([TextChunk(index=0, content="Hello world")]),  # type: ignore[arg-type]
    )
    command = make_command(
        source_entity_id=uuid.uuid4(),
    )

    source = await service.index_source(command)

    repository.get_source.assert_awaited_once()
    repository.add_source.assert_awaited_once()
    repository.add_chunks.assert_awaited_once()
    session.commit.assert_awaited_once_with()
    assert source.title == "Task title"
    assert source.raw_content == "Hello world"
    assert source.embedding_model == "test-embedding"
    add_chunks_call = repository.add_chunks.await_args
    assert add_chunks_call is not None
    assert add_chunks_call.args[0][0].content == "Hello world"


@pytest.mark.asyncio
async def test_index_source_skips_unchanged_existing_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_source = KnowledgeSource(
        organization_id=uuid.uuid4(),
        source_type="task",
        source_entity_id=uuid.uuid4(),
        title="Existing",
        raw_content="Hello world",
        source_metadata={},
        content_hash="64ec88ca00b268e5ba1a35678a1b5316d212f4f366b2477232534a8aeca37f3c",
    )
    session = FakeSession()
    repository = FakeRepository(session, existing_source=existing_source)

    monkeypatch.setattr(
        "src.ingestion.service.KnowledgeRepository",
        lambda session: repository,
    )

    service = IngestionService(
        session=session,  # type: ignore[arg-type]
        embedding_provider=FakeEmbeddingProvider([[0.1, 0.2]]),  # type: ignore[arg-type]
        chunker=TextChunker(),
    )

    source = await service.index_source(
        make_command(
            source_entity_id=existing_source.source_entity_id,
        )
    )

    assert source is existing_source
    repository.add_source.assert_not_awaited()
    repository.add_chunks.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_index_source_raises_when_provider_returns_wrong_vector_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    repository = FakeRepository(session)

    monkeypatch.setattr(
        "src.ingestion.service.KnowledgeRepository",
        lambda session: repository,
    )

    service = IngestionService(
        session=session,  # type: ignore[arg-type]
        embedding_provider=FakeEmbeddingProvider([]),  # type: ignore[arg-type]
        chunker=FakeChunker([TextChunk(index=0, content="Hello world")]),  # type: ignore[arg-type]
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected number of vectors",
    ):
        await service.index_source(
            make_command(
                source_entity_id=uuid.uuid4(),
            )
        )

    repository.add_source.assert_not_awaited()
    session.commit.assert_not_awaited()
