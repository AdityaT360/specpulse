"""add generated test cases

Revision ID: 0003_add_test_cases
Revises: 0002_add_specs_and_endpoints
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_add_test_cases"
down_revision: str | None = "0002_add_specs_and_endpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "endpoint_id",
            sa.Integer(),
            sa.ForeignKey("endpoints.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("expected_status", sa.Integer(), nullable=False),
        sa.Column("path_params", sa.JSON(), nullable=False),
        sa.Column("query_params", sa.JSON(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_test_cases_endpoint_id", "test_cases", ["endpoint_id"])


def downgrade() -> None:
    op.drop_index("ix_test_cases_endpoint_id", table_name="test_cases")
    op.drop_table("test_cases")
