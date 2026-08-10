import uuid

from pydantic import BaseModel, Field


class IndexSourceCommand(BaseModel):
    organization_id: uuid.UUID
    project_id: uuid.UUID | None = None

    source_type: str = Field(
        min_length=1,
        max_length=50,
    )

    source_entity_id: uuid.UUID | None = None

    title: str = Field(
        min_length=1,
        max_length=500,
    )

    content: str = Field(
        min_length=1,
    )

    metadata: dict[str, object] = Field(
        default_factory=dict,
    )
