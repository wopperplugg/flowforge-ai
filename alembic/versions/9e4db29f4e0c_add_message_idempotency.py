"""add message idempotency

Revision ID: 9e4db29f4e0c
Revises: de1c0d4107e3
Create Date: 2026-08-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9e4db29f4e0c"
down_revision: str | Sequence[str] | None = "de1c0d4107e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_sources",
        sa.Column(
            "source_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )

    op.create_table(
        "processed_message_events",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_processed_message_events")),
    )
    op.create_index(
        "ix_processed_message_events_aggregate",
        "processed_message_events",
        ["organization_id", "aggregate_type", "aggregate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processed_message_events_aggregate",
        table_name="processed_message_events",
    )
    op.drop_table("processed_message_events")
    op.drop_column("knowledge_sources", "source_version")
