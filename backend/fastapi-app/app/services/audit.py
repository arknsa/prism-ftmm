"""Audit-write service contract (P1.14).

Defines write_audit_entry(), the single point of entry for all AUDIT_LOG writes.
The function adds an entry to the session but does NOT flush or commit — the caller
owns the transaction boundary, which allows audit entries to be batched atomically
with the mutating operation they describe (Phase 4 pattern, D-025, D-031).

Decisions: D-025, D-031, D-036.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def write_audit_entry(
    session: Session,
    *,
    table_name: str,
    record_id: str,
    action_type: str,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    changed_by: int | None = None,
) -> AuditLog:
    """Add one AUDIT_LOG entry to the session without flushing or committing.

    Args:
        session: Active SQLAlchemy session. The caller is responsible for commit.
        table_name: Name of the table whose row was mutated (e.g. "alumni").
        record_id: Stringified primary key of the mutated row (e.g. "42").
        action_type: One of "INSERT", "UPDATE", or "DELETE".
        old_values: Snapshot of the row before mutation; None for INSERT.
        new_values: Snapshot of the row after mutation; None for DELETE.
        changed_by: AppUser.user_id of the actor; None for system/script actions.

    Returns:
        The AuditLog instance added to the session (not yet persisted).
    """
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action_type=action_type,
        old_values=old_values,
        new_values=new_values,
        changed_by=changed_by,
    )
    session.add(entry)
    return entry
