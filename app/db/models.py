from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    specs: Mapped[list["UploadedSpec"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class UploadedSpec(Base):
    __tablename__ = "uploaded_specs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    openapi_version: Mapped[str] = mapped_column(String(30), nullable=False)
    raw_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="specs")
    endpoints: Mapped[list["Endpoint"]] = relationship(
        back_populates="spec",
        cascade="all, delete-orphan",
    )


class Endpoint(Base):
    __tablename__ = "endpoints"
    __table_args__ = (
        UniqueConstraint("spec_id", "path", "method", name="uq_endpoints_spec_path_method"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[int] = mapped_column(
        ForeignKey("uploaded_specs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    request_body: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    responses: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    has_request_body: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    spec: Mapped[UploadedSpec] = relationship(back_populates="endpoints")
