"""Bootstrap the first administrator (H3 R1 — local end-to-end enablement).

Creates the initial Admin so a human can log in and then manage all other users
from the app. It performs the two sync steps the provisioning service normally
does (D-043), but for the very first user where no actor exists yet:

  1. create (or reuse) a Supabase Auth user via the Admin API, and
  2. insert a matching APP_USER row mapped to the seeded 'Admin' role.

This adds NO new API endpoint, NO schema change, and does NOT alter the auth
flow — it only writes the two rows the running system already expects. Roles and
permissions must exist first: run ``seed_rbac.py`` before this script.

Prerequisites (environment):
    DATABASE_URL                Supabase Postgres URL (pooler)
    SUPABASE_URL                Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY   service-role key (Admin API)
    ADMIN_EMAIL                 email for the first admin
    ADMIN_PASSWORD              initial password (change after first login)

Usage (from backend/fastapi-app so the venv resolves deps):
    DATABASE_URL=... SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \\
        ADMIN_EMAIL=admin@ftmm.ac.id ADMIN_PASSWORD='ChangeMe!23' \\
        uv run python ../../scripts/imports/bootstrap_admin.py

Idempotent:
  - Supabase user: reused if the email is already registered.
  - APP_USER: ON CONFLICT (supabase_uuid) DO NOTHING.

Exit codes:
    0  success
    1  missing configuration
    2  'Admin' role not found (run seed_rbac.py first)
"""

from __future__ import annotations

import os
import sys

from _utils import normalize_db_url
from sqlalchemy import create_engine, text
from supabase import Client, create_client

_ADMIN_ROLE = "Admin"

_SELECT_ROLE_ID = text("SELECT role_id FROM role WHERE role_name = :role_name")
_UPSERT_APP_USER = text(
    "INSERT INTO app_user (supabase_uuid, role_id, email, is_active) "
    "VALUES (:uuid, :role_id, :email, TRUE) "
    "ON CONFLICT (supabase_uuid) DO NOTHING RETURNING user_id"
)


def _get_or_create_supabase_user(supabase: Client, email: str, password: str) -> str:
    """Return the Supabase user id, creating the auth user if it doesn't exist."""
    try:
        response = supabase.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
        return str(response.user.id)
    except Exception as exc:  # map "already registered" to reuse (idempotent)
        message = str(exc)
        if "already been registered" not in message and "already exists" not in message:
            raise
        # Idempotent path: the email is registered — locate the existing user.
        for user in supabase.auth.admin.list_users():
            if getattr(user, "email", None) == email:
                return str(user.id)
        raise RuntimeError(
            f"Email {email!r} is already registered in Supabase but could not be located."
        ) from exc


def bootstrap(
    *,
    database_url: str,
    supabase_url: str,
    service_role_key: str,
    email: str,
    password: str,
) -> None:
    supabase = create_client(supabase_url, service_role_key)
    supabase_uuid = _get_or_create_supabase_user(supabase, email, password)

    engine = create_engine(normalize_db_url(database_url), future=True)
    with engine.begin() as conn:
        role_id = conn.execute(
            _SELECT_ROLE_ID, {"role_name": _ADMIN_ROLE}
        ).scalar_one_or_none()
        if role_id is None:
            print(
                "ERROR: 'Admin' role not found. Run seed_rbac.py first.",
                file=sys.stderr,
            )
            sys.exit(2)
        user_id = conn.execute(
            _UPSERT_APP_USER,
            {"uuid": supabase_uuid, "role_id": role_id, "email": email},
        ).scalar_one_or_none()

    state = "created" if user_id is not None else "already present"
    print(
        f"bootstrap_admin: Admin APP_USER {state} for {email} "
        f"(supabase_uuid={supabase_uuid})."
    )


def main() -> None:
    required = [
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
    ]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        print(
            f"ERROR: missing environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)
    bootstrap(
        database_url=os.environ["DATABASE_URL"],
        supabase_url=os.environ["SUPABASE_URL"],
        service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        email=os.environ["ADMIN_EMAIL"],
        password=os.environ["ADMIN_PASSWORD"],
    )


if __name__ == "__main__":
    main()
