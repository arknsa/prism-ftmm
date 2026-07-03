"""Audit log model.

Every mutation that passes through FastAPI must produce an AUDIT_LOG entry
(D-025, D-036). The write service contract is defined in Phase 1 S4 (P1.14);
wiring to business operations happens in Phase 4 (P4.6).

changed_by is nullable to accommodate system/script mutations that occur before
the auth layer (Phase 2) is in place.

Decisions: D-025, D-036; Q-023 (FK to APP_USER declared explicitly).
"""

from __future__ import annotations

import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditLog(Base):
    """Immutable audit trail entry for every data mutation (D-025).

    old_values is NULL for INSERT operations.
    new_values is NULL for DELETE operations.
    changed_by is NULL for system/script actions pre-auth-layer.
    """

    __tablename__ = "audit_log"

    audit_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    record_id: Mapped[str] = mapped_column(
        sa.String(100), nullable=False
    )  # stringified PK of mutated row
    action_type: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )  # "INSERT" | "UPDATE" | "DELETE"
    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey("app_user.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at: Mapped[datetime.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
