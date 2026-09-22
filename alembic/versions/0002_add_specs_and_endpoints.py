"""add uploaded specs and endpoints

Revision ID: 0002_add_specs_and_endpoints
Revises: 0001_create_projects
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_add_specs_and_endpoints"
down_revision: str | None = "0001_create_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploaded_specs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("openapi_version", sa.String(length=30), nullable=False),
        sa.Column("raw_spec", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_uploaded_specs_project_id", "uploaded_specs", ["project_id"])

    op.create_table(
        "endpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "spec_id",
            sa.Integer(),
            sa.ForeignKey("uploaded_specs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("operation_id", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("request_body", sa.JSON(), nullable=True),
        sa.Column("responses", sa.JSON(), nullable=False),
        sa.Column("has_request_body", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "spec_id",
            "path",
            "method",
            name="uq_endpoints_spec_path_method",
        ),
    )
    op.create_index("ix_endpoints_spec_id", "endpoints", ["spec_id"])


def downgrade() -> None:
    op.drop_index("ix_endpoints_spec_id", table_name="endpoints")
    op.drop_table("endpoints")
    op.drop_index("ix_uploaded_specs_project_id", table_name="uploaded_specs")
    op.drop_table("uploaded_specs")
