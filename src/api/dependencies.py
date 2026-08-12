from typing import Annotated

from fastapi import Depends
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.approval_service import AssistantApprovalService
from src.agents.project_service import ProjectAssistantService
from src.agents.rag.service import RAGAssistantService
from src.api.auth import AuthenticatedContext, get_authenticated_context
from src.config import settings
from src.embeddings.ollama import OllamaEmbeddingProvider
from src.flowforge_api.client import FlowForgeAPIClient
from src.infrastructure.database.session import get_session

assistant_checkpointer = InMemorySaver()


async def get_embedding_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )


async def get_rag_assistant_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RAGAssistantService:
    return RAGAssistantService(
        session=session,
        embedding_provider=await get_embedding_provider(),
        checkpointer=assistant_checkpointer,
    )


async def get_flowforge_api_client(
    auth_context: Annotated[
        AuthenticatedContext,
        Depends(get_authenticated_context),
    ],
) -> FlowForgeAPIClient:
    return FlowForgeAPIClient(
        base_url=settings.flowforge_api_base_url,
        access_token=auth_context.access_token,
        timeout_seconds=settings.flowforge_api_timeout_seconds,
    )


async def get_project_assistant_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    flowforge_client: Annotated[
        FlowForgeAPIClient,
        Depends(get_flowforge_api_client),
    ],
) -> ProjectAssistantService:
    return ProjectAssistantService(
        session=session,
        embedding_provider=await get_embedding_provider(),
        flowforge_client=flowforge_client,
    )


async def get_assistant_approval_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    flowforge_client: Annotated[
        FlowForgeAPIClient,
        Depends(get_flowforge_api_client),
    ],
) -> AssistantApprovalService:
    return AssistantApprovalService(
        session=session,
        flowforge_client=flowforge_client,
    )
