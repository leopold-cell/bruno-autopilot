"""init: keywords + content_runs

Revision ID: 0001
Revises:
Create Date: 2026-06-08

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "keywords",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("keyword", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("intent", sa.String(length=80), nullable=True),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("slug", sa.String(length=200), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="ideation"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_keywords_keyword", "keywords", ["keyword"])
    op.create_index("ix_keywords_keyword", "keywords", ["keyword"])
    op.create_index("ix_keywords_status", "keywords", ["status"])

    op.create_table(
        "content_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("keyword_id", sa.String(length=36), nullable=True),
        sa.Column("keyword", sa.String(length=300), nullable=True),
        sa.Column("slug", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("qa_passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("qa_issues", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_content_runs_keyword_id", "content_runs", ["keyword_id"])


def downgrade() -> None:
    op.drop_table("content_runs")
    op.drop_table("keywords")
