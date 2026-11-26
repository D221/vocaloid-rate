"""Add request_metrics table

Revision ID: a1b2c3d4e5f6
Revises: c02033ae2a24
Create Date: 2026-11-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c02033ae2a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "request_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("route", sa.String(length=200), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("ua_class", sa.String(length=10), nullable=False),
        sa.Column("cpu_ms", sa.Float(), nullable=False),
        sa.Column("bytes_sent", sa.Integer(), nullable=False),
        sa.Column("is_cold_start", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_request_metrics_id"), "request_metrics", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_request_metrics_created_at"),
        "request_metrics",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_request_metrics_created_at"), table_name="request_metrics")
    op.drop_index(op.f("ix_request_metrics_id"), table_name="request_metrics")
    op.drop_table("request_metrics")
