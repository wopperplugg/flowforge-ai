import asyncio
import uuid

from src.agents.rag.graph import create_rag_graph
from src.agents.rag.nodes import (
    create_generate_node,
    create_grade_documents_node,
    create_retrieve_node,
    create_rewrite_query_node,
)
from src.config import settings
from src.embeddings.ollama import OllamaEmbeddingProvider
from src.infrastructure.database.session import async_session_factory


async def main() -> None:
    organization_id = uuid.UUID("c2128df2-54b9-4a15-87de-f2c788e4a4d3")

    project_id = uuid.UUID("bad272c0-f3ac-4ae2-8aed-5a298c3cb983")

    embedding_provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )

    async with async_session_factory() as session:
        retrieve_node = create_retrieve_node(
            session=session,
            embedding_provider=embedding_provider,
            organization_id=organization_id,
            project_id=project_id,
        )

        grade_documents_node = create_grade_documents_node()
        generate_node = create_generate_node()
        rewrite_query_node = create_rewrite_query_node()

        graph = create_rag_graph(
            retrieve_node=retrieve_node,
            grade_documents_node=grade_documents_node,
            generate_node=generate_node,
            rewrite_query_node=rewrite_query_node,
        )

        result = await graph.ainvoke(
            {
                "messages": [],
                "query": "How does Kubernetes deployment work in this project?",
                "documents": [],
                "documents_relevant": False,
                "answer": "",
                "rewrite_count": 0,
            }
        )

        print("Query:")
        print(result["query"])

        print("\nRelevant:")
        print(result["documents_relevant"])

        print("\nRewrite count:")
        print(result["rewrite_count"])

        print("\nAnswer:")
        print(result["answer"])

        print("\nDocuments:")
        for document in result["documents"]:
            print("=" * 80)
            print(document.page_content)
            print(document.metadata)


if __name__ == "__main__":
    asyncio.run(main())
