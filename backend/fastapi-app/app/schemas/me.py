"""Response schema for the /me identity endpoint (P2.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MeResponse(BaseModel):
    """Authenticated user's identity and authorization summary.

    Returned by GET /me. Contains everything the frontend needs to
    drive role-gated UI without making additional API calls (S4/S5).

    Permissions are returned as a sorted list for stable serialization;
    the consuming frontend may convert to a Set for O(1) lookups.
    """

    user_id: int = Field(..., description="APP_USER primary key.")
    supabase_uuid: str = Field(..., description="Supabase user UUID (matches JWT sub).")
    role: str = Field(..., description="Assigned role name (e.g. 'Admin').")
    permissions: list[str] = Field(
        ...,
        description="Sorted list of permission names granted to this user's role.",
    )
