"""add load test summaries

Revision ID: 0005_add_load_tests
Revises: 0004_add_test_runs
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_add_load_tests"
down_revision: str | None = "0004_add_test_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "load_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "test_case_id",
            sa.Integer(),
            sa.ForeignKey("test_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_base_url", sa.String(length=500), nullable=False),
        sa.Column("users", sa.Integer(), nullable=False),
        sa.Column("spawn_rate", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_requests", sa.Integer(), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=True),
        sa.Column("failure_percentage", sa.Float(), nullable=True),
        sa.Column("average_latency_ms", sa.Float(), nullable=True),
        sa.Column("p95_latency_ms", sa.Float(), nullable=True),
        sa.Column("requests_per_second", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_load_tests_project_id", "load_tests", ["project_id"])
    op.create_index("ix_load_tests_test_case_id", "load_tests", ["test_case_id"])


def downgrade() -> None:
    op.drop_index("ix_load_tests_test_case_id", table_name="load_tests")
    op.drop_index("ix_load_tests_project_id", table_name="load_tests")
    op.drop_table("load_tests")
