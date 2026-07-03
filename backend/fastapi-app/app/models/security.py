"""RBAC security models.

APP_USER is keyed by the Supabase user UUID — Supabase Auth handles authentication,
the app DB handles authorization (D-043). No JWT verification here; that is Phase 2.

Decisions: D-026, D-032, D-036, D-043.
"""

from __future__ import annotations

import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Role(Base):
    """Application role (D-026). Four roles: Admin, Data Curator, Faculty Viewer, Read Only."""

    __tablename__ = "role"

    role_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(sa.String(50), nullable=False, unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class Permission(Base):
    """Granular permission name (D-026, D-036). Assigned to roles via RolePermission."""

    __tablename__ = "permission"

    permission_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    permission_name: Mapped[str] = mapped_column(sa.String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class RolePermission(Base):
    """Many-to-many join between Role and Permission (D-026)."""

    __tablename__ = "role_permission"
    __table_args__ = (sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("role.role_id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("permission.permission_id", ondelete="CASCADE"),
        nullable=False,
    )


class AppUser(Base):
    """Application user keyed by the Supabase Auth user UUID (D-043).

    supabase_uuid is the canonical identity bridge between Supabase Auth (authentication)
    and the app DB (authorization). The only sync point is user provisioning: an Admin
    creates a Supabase Auth user AND a matching AppUser row + role assignment (Phase 2, P2.4).

    email is a convenience denormalized copy; Supabase Auth is the source of truth for identity.
    """

    __tablename__ = "app_user"

    user_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    supabase_uuid: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, unique=True)
    role_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("role.role_id", ondelete="RESTRICT"), nullable=False
    )
    email: Mapped[str | None] = mapped_column(sa.String(320), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    created_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
