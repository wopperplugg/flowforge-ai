import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.agents.approval_service import (
    AssistantApprovalService,
    ToolApprovalInvalidStateError,
    ToolApprovalNotFoundError,
)
from src.agents.project_service import (
    ProjectAssistantExecutionError,
    ProjectAssistantService,
    ProjectAssistantTimeoutError,
)
from src.agents.rag.schemas import (
    AssistantQueryRequest,
    AssistantQueryResponse,
    ProjectAssistantQueryRequest,
    ProjectAssistantQueryResponse,
    ToolApprovalExecutionResponse,
    ToolApprovalResponse,
)
from src.agents.rag.service import (
    AssistantExecutionError,
    AssistantTimeoutError,
    RAGAssistantService,
)
from src.api.auth import AuthenticatedContext, get_authenticated_context
from src.api.dependencies import (
    get_assistant_approval_service,
    get_project_assistant_service,
    get_rag_assistant_service,
)

router = APIRouter(
    prefix="/assistant",
    tags=["assistant"],
)
PROJECT_AGENT_TIMEOUT_EVENT = (
    'event: error\ndata: {"detail":"Project assistant request timed out"}\n\n'
)
PROJECT_AGENT_EXECUTION_ERROR_EVENT = (
    'event: error\ndata: {"detail":"Project assistant execution failed"}\n\n'
)


@router.post(
    "/query",
    response_model=AssistantQueryResponse,
    status_code=status.HTTP_200_OK,
)
async def query_assistant(
    payload: AssistantQueryRequest,
    auth_context: Annotated[
        AuthenticatedContext,
        Depends(get_authenticated_context),
    ],
    assistant_service: Annotated[
        RAGAssistantService,
        Depends(get_rag_assistant_service),
    ],
) -> AssistantQueryResponse:
    try:
        return await assistant_service.query(
            organization_id=auth_context.organization_id,
            project_id=payload.project_id,
            user_id=auth_context.user_id,
            question=payload.question,
            thread_id=payload.thread_id,
        )
    except AssistantTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Assistant request timed out",
        ) from exc
    except AssistantExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Assistant execution failed",
        ) from exc


@router.post(
    "/agent/query",
    response_model=ProjectAssistantQueryResponse,
    status_code=status.HTTP_200_OK,
)
async def query_project_agent(
    payload: ProjectAssistantQueryRequest,
    auth_context: Annotated[
        AuthenticatedContext,
        Depends(get_authenticated_context),
    ],
    assistant_service: Annotated[
        ProjectAssistantService,
        Depends(get_project_assistant_service),
    ],
) -> ProjectAssistantQueryResponse:
    try:
        return await assistant_service.query(
            organization_id=auth_context.organization_id,
            project_id=payload.project_id,
            user_id=auth_context.user_id,
            question=payload.question,
            thread_id=payload.thread_id,
            allow_write_tools=payload.allow_write_tools,
        )
    except ProjectAssistantTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Project assistant request timed out",
        ) from exc
    except ProjectAssistantExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Project assistant execution failed",
        ) from exc


@router.post(
    "/agent/stream",
    status_code=status.HTTP_200_OK,
)
async def stream_project_agent(
    payload: ProjectAssistantQueryRequest,
    auth_context: Annotated[
        AuthenticatedContext,
        Depends(get_authenticated_context),
    ],
    assistant_service: Annotated[
        ProjectAssistantService,
        Depends(get_project_assistant_service),
    ],
) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        yield "event: start\ndata: {}\n\n"
        try:
            result = await assistant_service.query(
                organization_id=auth_context.organization_id,
                project_id=payload.project_id,
                user_id=auth_context.user_id,
                question=payload.question,
                thread_id=payload.thread_id,
                allow_write_tools=payload.allow_write_tools,
            )
        except ProjectAssistantTimeoutError:
            yield PROJECT_AGENT_TIMEOUT_EVENT
            return
        except ProjectAssistantExecutionError:
            yield PROJECT_AGENT_EXECUTION_ERROR_EVENT
            return

        yield f"event: final\ndata: {result.model_dump_json()}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
    )


@router.post(
    "/approvals/{approval_id}/approve",
    response_model=ToolApprovalResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_tool_call(
    approval_id: str,
    auth_context: Annotated[
        AuthenticatedContext,
        Depends(get_authenticated_context),
    ],
    approval_service: Annotated[
        AssistantApprovalService,
        Depends(get_assistant_approval_service),
    ],
) -> ToolApprovalResponse:
    try:
        return await approval_service.approve(
            approval_id=_approval_uuid(approval_id),
            organization_id=auth_context.organization_id,
            user_id=auth_context.user_id,
        )
    except ToolApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ToolApprovalInvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/approvals/{approval_id}/reject",
    response_model=ToolApprovalResponse,
    status_code=status.HTTP_200_OK,
)
async def reject_tool_call(
    approval_id: str,
    auth_context: Annotated[
        AuthenticatedContext,
        Depends(get_authenticated_context),
    ],
    approval_service: Annotated[
        AssistantApprovalService,
        Depends(get_assistant_approval_service),
    ],
) -> ToolApprovalResponse:
    try:
        return await approval_service.reject(
            approval_id=_approval_uuid(approval_id),
            organization_id=auth_context.organization_id,
            user_id=auth_context.user_id,
        )
    except ToolApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ToolApprovalInvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/approvals/{approval_id}/execute",
    response_model=ToolApprovalExecutionResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_tool_call(
    approval_id: str,
    auth_context: Annotated[
        AuthenticatedContext,
        Depends(get_authenticated_context),
    ],
    approval_service: Annotated[
        AssistantApprovalService,
        Depends(get_assistant_approval_service),
    ],
) -> ToolApprovalExecutionResponse:
    try:
        return await approval_service.execute(
            approval_id=_approval_uuid(approval_id),
            organization_id=auth_context.organization_id,
            user_id=auth_context.user_id,
        )
    except ToolApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ToolApprovalInvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _approval_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid approval id") from exc
