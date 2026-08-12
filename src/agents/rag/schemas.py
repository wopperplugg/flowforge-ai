import uuid

from pydantic import BaseModel, Field


class AssistantQueryRequest(BaseModel):
    project_id: uuid.UUID
    question: str = Field(
        min_length=1,
        max_length=4000,
    )
    thread_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )


class AssistantSource(BaseModel):
    source_id: uuid.UUID | None = None
    source_type: str | None = None
    source_entity_id: uuid.UUID | None = None
    source_title: str | None = None
    chunk_index: int | None = None
    url: str | None = None


class AssistantQueryResponse(BaseModel):
    answer: str
    thread_id: str
    query: str
    rewrite_count: int
    documents_relevant: bool
    sources: list[AssistantSource]


class ProjectAssistantQueryRequest(BaseModel):
    project_id: uuid.UUID
    question: str = Field(
        min_length=1,
        max_length=4000,
    )
    thread_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    allow_write_tools: bool = False


class ProjectAssistantQueryResponse(BaseModel):
    answer: str
    thread_id: str
    write_tools_enabled: bool


class ToolApprovalResponse(BaseModel):
    id: uuid.UUID
    thread_id: str
    tool_name: str
    arguments: dict[str, object]
    status: str
    result: dict[str, object] | None = None


class ToolApprovalExecutionResponse(BaseModel):
    approval: ToolApprovalResponse
    result: dict[str, object]
