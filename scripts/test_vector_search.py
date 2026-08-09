import asyncio
import hashlib
import uuid

from sqlalchemy import delete

from src.config import settings
from src.embeddings.ollama import OllamaEmbeddingProvider
from src.infrastructure.database.session import async_session_factory
from src.knowledge.models import KnowledgeChunk, KnowledgeSource
from src.knowledge.repository import KnowledgeRepository


async def main() -> None:
    provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )

    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()

    documents = [
        "JWT authentication and refresh token rotation",
        "PostgreSQL indexes improve database query performance",
        "RabbitMQ processes asynchronous messages",
    ]

    embeddings = await provider.embed_documents(documents)

    async with async_session_factory() as session:
        await session.execute(delete(KnowledgeChunk))
        await session.execute(delete(KnowledgeSource))

        repository = KnowledgeRepository(session)

        raw_content = "\n".join(documents)

        source = KnowledgeSource(
            organization_id=organization_id,
            project_id=project_id,
            source_type="test",
            source_entity_id=uuid.uuid4(),
            title="Ollama semantic search test",
            raw_content=raw_content,
            content_hash=hashlib.sha256(
                raw_content.encode(),
            ).hexdigest(),
            embedding_model=settings.embedding_model,
        )

        await repository.add_source(source)

        chunks = [
            KnowledgeChunk(
                source_id=source.id,
                organization_id=organization_id,
                project_id=project_id,
                chunk_index=index,
                content=content,
                content_hash=hashlib.sha256(
                    content.encode(),
                ).hexdigest(),
                embedding=embedding,
            )
            for index, (content, embedding) in enumerate(
                zip(documents, embeddings, strict=True),
            )
        ]

        await repository.add_chunks(chunks)
        await session.commit()

        question = "How does authentication work?"

        query_embedding = await provider.embed_text(question)

        results = await repository.search_similar(
            organization_id=organization_id,
            project_id=project_id,
            embedding=query_embedding,
            limit=3,
        )

        print("Question:", question)
        print()

        for chunk in results:
            print("-", chunk.content)


if __name__ == "__main__":
    asyncio.run(main())