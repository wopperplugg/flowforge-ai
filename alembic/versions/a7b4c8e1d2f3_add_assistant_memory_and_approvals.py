"""add assistant memory and approvals

Revision ID: a7b4c8e1d2f3
Revises: 9e4db29f4e0c
Create Date: 2026-08-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7b4c8e1d2f3"
down_revision: str | Sequence[str] | None = "9e4db29f4e0c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_threads",
        sa.Column("id", sa.String(length=200), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_threads")),
    )
    op.create_index(
        op.f("ix_assistant_threads_organization_id"),
        "assistant_threads",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_assistant_threads_organization_user",
        "assistant_threads",
        ["organization_id", "user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_threads_project_id"),
        "assistant_threads",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_threads_user_id"),
        "assistant_threads",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "message_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["assistant_threads.id"],
            name=op.f("fk_assistant_messages_thread_id_assistant_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_messages")),
    )
    op.create_index(
        op.f("ix_assistant_messages_thread_id"),
        "assistant_messages",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        "ix_assistant_messages_thread_created",
        "assistant_messages",
        ["thread_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "assistant_tool_approvals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thread_id", sa.String(length=200), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column(
            "arguments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["assistant_threads.id"],
            name=op.f("fk_assistant_tool_approvals_thread_id_assistant_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assistant_tool_approvals")),
    )
    op.create_index(
        op.f("ix_assistant_tool_approvals_organization_id"),
        "assistant_tool_approvals",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_assistant_tool_approvals_organization_user",
        "assistant_tool_approvals",
        ["organization_id", "user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_tool_approvals_project_id"),
        "assistant_tool_approvals",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_tool_approvals_thread_id"),
        "assistant_tool_approvals",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        "ix_assistant_tool_approvals_thread_status",
        "assistant_tool_approvals",
        ["thread_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assistant_tool_approvals_user_id"),
        "assistant_tool_approvals",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assistant_tool_approvals_user_id"),
        table_name="assistant_tool_approvals",
    )
    op.drop_index(
        "ix_assistant_tool_approvals_thread_status",
        table_name="assistant_tool_approvals",
    )
    op.drop_index(
        op.f("ix_assistant_tool_approvals_thread_id"),
        table_name="assistant_tool_approvals",
    )
    op.drop_index(
        op.f("ix_assistant_tool_approvals_project_id"),
        table_name="assistant_tool_approvals",
    )
    op.drop_index(
        "ix_assistant_tool_approvals_organization_user",
        table_name="assistant_tool_approvals",
    )
    op.drop_index(
        op.f("ix_assistant_tool_approvals_organization_id"),
        table_name="assistant_tool_approvals",
    )
    op.drop_table("assistant_tool_approvals")
    op.drop_index(
        "ix_assistant_messages_thread_created",
        table_name="assistant_messages",
    )
    op.drop_index(
        op.f("ix_assistant_messages_thread_id"),
        table_name="assistant_messages",
    )
    op.drop_table("assistant_messages")
    op.drop_index(op.f("ix_assistant_threads_user_id"), table_name="assistant_threads")
    op.drop_index(
        op.f("ix_assistant_threads_project_id"),
        table_name="assistant_threads",
    )
    op.drop_index(
        "ix_assistant_threads_organization_user",
        table_name="assistant_threads",
    )
    op.drop_index(
        op.f("ix_assistant_threads_organization_id"),
        table_name="assistant_threads",
    )
    op.drop_table("assistant_threads")
