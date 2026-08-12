import asyncio
import uuid

from src.agents.tools.knowledge import (
    create_search_project_knowledge_tool,
)
from src.config import settings
from src.embeddings.ollama import OllamaEmbeddingProvider
from src.infrastructure.database.session import async_session_factory


async def main() -> None:
    organization_id = uuid.UUID(
        "c2128df2-54b9-4a15-87de-f2c788e4a4d3"
    )

    project_id = uuid.UUID(
        "bad272c0-f3ac-4ae2-8aed-5a298c3cb983"
    )

    embedding_provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )

    async with async_session_factory() as session:
        search_tool = create_search_project_knowledge_tool(
            session=session,
            embedding_provider=embedding_provider,
            organization_id=organization_id,
            project_id=project_id,
        )

        result = await search_tool.ainvoke(
            {
                "query": "authentication",
            }
        )

        print(result)


if __name__ == "__main__":
    asyncio.run(main())