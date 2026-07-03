"""Request/response schemas for user-provisioning endpoints (P2.4).

POST /users  — provision a new application user (Admin-only)
DELETE /users/{user_id} — deactivate an existing application user (Admin-only)

Design (D-043): Supabase Auth is the identity provider; the app DB is the
authorization store. The only sync point is provisioning: the Admin creates
a Supabase Auth user AND the matching APP_USER row in a single API call.
The initial password is passed to Supabase and never stored in the app DB.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreateRequest(BaseModel):
    """Body for POST /users.

    email and password are forwarded to Supabase Auth. role_name selects one
    of the four seeded roles (Admin, Data Curator, Faculty Viewer, Read Only).
    """

    email: EmailStr = Field(..., description="Email address for the new Supabase Auth user.")
    password: str = Field(
        ...,
        min_length=8,
        description=(
            "Initial password passed directly to Supabase Auth. "
            "Never stored in the application database."
        ),
    )
    role_name: str = Field(
        ...,
        description=(
            "One of the four seeded role names: "
            "'Admin', 'Data Curator', 'Faculty Viewer', 'Read Only'."
        ),
    )


class UserCreateResponse(BaseModel):
    """Response body for a successful POST /users (HTTP 201)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(..., description="APP_USER primary key.")
    supabase_uuid: str = Field(..., description="Supabase Auth user UUID.")
    email: str | None = Field(..., description="Email stored in APP_USER.")
    role: str = Field(..., description="Assigned role name.")


class UserDeactivateResponse(BaseModel):
    """Response body for a successful DELETE /users/{user_id} (HTTP 200)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(..., description="APP_USER primary key of the deactivated user.")
    supabase_uuid: str = Field(..., description="Supabase Auth user UUID that was banned.")
    is_active: bool = Field(..., description="Always False after successful deactivation.")
    detail: str = Field(..., description="Human-readable confirmation message.")
