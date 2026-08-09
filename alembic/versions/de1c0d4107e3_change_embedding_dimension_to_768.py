from typing import Sequence, Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op


revision: str = "de1c0d4107e3"
down_revision: Union[str, Sequence[str], None] = "6aec1997cc56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column(
        "knowledge_chunks",
        "embedding",
    )

    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.vector.VECTOR(dim=768),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "knowledge_chunks",
        "embedding",
    )

    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.vector.VECTOR(dim=1536),
            nullable=False,
        ),
    )