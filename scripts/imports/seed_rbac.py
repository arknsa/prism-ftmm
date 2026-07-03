"""Seed ROLE, PERMISSION, and ROLE_PERMISSION tables (D-026, D-036, D-043).

Inserts four roles and fourteen permissions, then maps them according to the
least-privilege matrix defined in docs/architecture/ROLE_PERMISSION_MATRIX.md.
This seed is the authoritative source of truth for Phase 2 enforcement code.

Usage:
    DATABASE_URL=postgresql+psycopg://... uv run python scripts/imports/seed_rbac.py

Idempotent:
  - Roles: ON CONFLICT (role_name) DO NOTHING
  - Permissions: ON CONFLICT (permission_name) DO NOTHING
  - RolePermissions: ON CONFLICT (role_id, permission_id) DO NOTHING
"""

from __future__ import annotations

import os
import sys

from _utils import normalize_db_url
from sqlalchemy import create_engine, text

ROLES: list[str] = [
    "Admin",
    "Data Curator",
    "Faculty Viewer",
    "Read Only",
]

PERMISSIONS: list[dict[str, str]] = [
    {"permission_name": "alumni:read", "description": "View validated alumni records"},
    {"permission_name": "alumni:write", "description": "Create/update alumni records"},
    {
        "permission_name": "alumni:validate",
        "description": "Approve or reject pending alumni",
    },
    {
        "permission_name": "alumni:delete",
        "description": "Delete or permanently reject alumni (Admin only)",
    },
    {"permission_name": "career:read", "description": "View career records"},
    {"permission_name": "career:write", "description": "Create/update career records"},
    {"permission_name": "company:read", "description": "View company and alias data"},
    {
        "permission_name": "company:write",
        "description": "Create/update company records and aliases",
    },
    {"permission_name": "import:run", "description": "Execute import pipeline"},
    {
        "permission_name": "dedup:review",
        "description": "Action items on deduplication queue",
    },
    {
        "permission_name": "snapshot:manage",
        "description": "Open/finalize a refresh snapshot",
    },
    {"permission_name": "audit:read", "description": "View audit log entries"},
    {
        "permission_name": "user:manage",
        "description": "Provision or deactivate application users",
    },
    {
        "permission_name": "analytics:read",
        "description": "Access aggregation and dashboard endpoints",
    },
]

# Role -> set of permission names.  Derived from ROLE_PERMISSION_MATRIX.md (D-036).
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "Admin": [
        "alumni:read",
        "alumni:write",
        "alumni:validate",
        "alumni:delete",
        "career:read",
        "career:write",
        "company:read",
        "company:write",
        "import:run",
        "dedup:review",
        "snapshot:manage",
        "audit:read",
        "user:manage",
        "analytics:read",
    ],
    "Data Curator": [
        "alumni:read",
        "alumni:write",
        "alumni:validate",
        "career:read",
        "career:write",
        "company:read",
        "company:write",
        "import:run",
        "dedup:review",
        "snapshot:manage",
        "analytics:read",
    ],
    "Faculty Viewer": [
        "alumni:read",
        "career:read",
        "company:read",
        "analytics:read",
    ],
    "Read Only": [
        "alumni:read",
        "career:read",
        "company:read",
        "analytics:read",
    ],
}

_INSERT_ROLE = text(
    "INSERT INTO role (role_name) VALUES (:role_name)"
    " ON CONFLICT (role_name) DO NOTHING RETURNING 1"
)
_INSERT_PERMISSION = text("""
    INSERT INTO permission (permission_name, description)
    VALUES (:permission_name, :description)
    ON CONFLICT (permission_name) DO NOTHING
    RETURNING 1
    """)
_SELECT_ROLE_ID = text("SELECT role_id FROM role WHERE role_name = :role_name")
_SELECT_PERM_ID = text(
    "SELECT permission_id FROM permission WHERE permission_name = :permission_name"
)
_INSERT_ROLE_PERM = text("""
    INSERT INTO role_permission (role_id, permission_id)
    VALUES (:role_id, :permission_id)
    ON CONFLICT (role_id, permission_id) DO NOTHING
    """)


def seed(database_url: str) -> None:
    engine = create_engine(normalize_db_url(database_url), future=True)
    with engine.begin() as conn:
        # 1. Roles
        role_rows = conn.execute(_INSERT_ROLE, [{"role_name": r} for r in ROLES])
        roles_inserted = len(role_rows.fetchall())

        # 2. Permissions
        perm_rows = conn.execute(_INSERT_PERMISSION, PERMISSIONS)
        perms_inserted = len(perm_rows.fetchall())

        # 3. Role-permission mappings
        mappings_inserted = 0
        for role_name, perm_names in ROLE_PERMISSIONS.items():
            role_id = conn.execute(
                _SELECT_ROLE_ID, {"role_name": role_name}
            ).scalar_one()
            for perm_name in perm_names:
                perm_id = conn.execute(
                    _SELECT_PERM_ID, {"permission_name": perm_name}
                ).scalar_one()
                result = conn.execute(
                    _INSERT_ROLE_PERM, {"role_id": role_id, "permission_id": perm_id}
                )
                mappings_inserted += result.rowcount

    print(
        f"seed_rbac: {roles_inserted} role(s), {perms_inserted} permission(s), "
        f"{mappings_inserted} mapping(s) inserted (0 each = already seeded)."
    )


def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    seed(url)


if __name__ == "__main__":
    main()
