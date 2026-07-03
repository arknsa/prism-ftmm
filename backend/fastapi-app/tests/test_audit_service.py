"""Unit tests for app.services.audit.write_audit_entry (P1.14).

Uses unittest.mock.MagicMock for the SQLAlchemy session so no database
connection is required. The function under test only calls session.add(),
making a mock the correct isolation boundary — no dialect-specific DDL
(e.g. JSONB) is exercised here.

Decisions: D-025, D-031, D-036.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call, create_autospec

from app.models.audit import AuditLog
from app.services.audit import write_audit_entry
from sqlalchemy.orm import Session


def _mock_session() -> MagicMock:
    """Return a spec-constrained mock of SQLAlchemy Session.

    create_autospec pins the mock to the real Session interface so that any
    unexpected attribute access (e.g. a misspelled method name) raises
    AttributeError instead of silently returning a new MagicMock. This makes
    assert_not_called() on flush/commit a meaningful assertion rather than a
    vacuously true one against an unspec'd mock.
    """
    return create_autospec(Session, instance=True)


# ---------------------------------------------------------------------------
# write_audit_entry — contract tests
# ---------------------------------------------------------------------------


def test_write_audit_entry_returns_audit_log_instance() -> None:
    """Return value is an AuditLog instance."""
    session = _mock_session()
    entry = write_audit_entry(
        session,
        table_name="alumni",
        record_id="1",
        action_type="INSERT",
        new_values={"full_name": "Budi Santoso"},
    )
    assert isinstance(entry, AuditLog)


def test_write_audit_entry_calls_session_add_exactly_once() -> None:
    """session.add() is called exactly once with the returned entry."""
    session = _mock_session()
    entry = write_audit_entry(
        session,
        table_name="alumni",
        record_id="1",
        action_type="INSERT",
    )
    session.add.assert_called_once_with(entry)


def test_write_audit_entry_does_not_flush_or_commit() -> None:
    """session.flush() and session.commit() must NOT be called."""
    session = _mock_session()
    write_audit_entry(
        session,
        table_name="alumni",
        record_id="1",
        action_type="INSERT",
    )
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_write_audit_entry_fields_match_arguments() -> None:
    """Returned AuditLog carries the exact values passed to the function."""
    session = _mock_session()
    old: dict[str, Any] = {"role_title": "Intern"}
    new: dict[str, Any] = {"role_title": "Engineer"}

    entry = write_audit_entry(
        session,
        table_name="career_record",
        record_id="42",
        action_type="UPDATE",
        old_values=old,
        new_values=new,
        changed_by=7,
    )

    assert entry.table_name == "career_record"
    assert entry.record_id == "42"
    assert entry.action_type == "UPDATE"
    assert entry.old_values is old
    assert entry.new_values is new
    assert entry.changed_by == 7


def test_write_audit_entry_nullable_fields_default_to_none() -> None:
    """old_values, new_values, and changed_by default to None when omitted."""
    session = _mock_session()
    entry = write_audit_entry(
        session,
        table_name="company",
        record_id="5",
        action_type="DELETE",
    )

    assert entry.old_values is None
    assert entry.new_values is None
    assert entry.changed_by is None


def test_write_audit_entry_multiple_calls_each_add_independently() -> None:
    """Calling write_audit_entry twice results in two separate session.add() calls."""
    session = _mock_session()

    entry_a = write_audit_entry(session, table_name="alumni", record_id="1", action_type="INSERT")
    entry_b = write_audit_entry(session, table_name="alumni", record_id="2", action_type="DELETE")

    assert entry_a is not entry_b
    assert session.add.call_count == 2
    session.add.assert_has_calls([call(entry_a), call(entry_b)])
