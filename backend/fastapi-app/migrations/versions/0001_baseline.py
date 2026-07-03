"""Empty baseline migration.

Establishes the Alembic version history with no schema changes. Models and tables are
introduced from Phase 1 onward (Schema v1 + D-040..D-051 deltas).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: Phase 0 baseline."""
    pass


def downgrade() -> None:
    """No-op: Phase 0 baseline."""
    pass
