"""Pydantic schemas for company and alias management (P4.6, P4.10)."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict


class CompanyOut(BaseModel):
    """Output schema for a Company."""

    model_config = ConfigDict(from_attributes=True)

    company_id: int
    canonical_name: str
    industry_id: int | None
    location_id: int | None
    created_at: datetime.datetime


class CompanyListOut(BaseModel):
    """List of companies."""

    total: int
    items: list[CompanyOut]


class CompanyUpdateIn(BaseModel):
    """Request body to update a company's industry and/or location assignment."""

    industry_id: int | None = None
    location_id: int | None = None


class CompanyAliasOut(BaseModel):
    """Output schema for a CompanyAlias."""

    model_config = ConfigDict(from_attributes=True)

    alias_id: int
    company_id: int
    alias_name: str
    source_id: int | None
    created_at: datetime.datetime


class CompanyAliasListOut(BaseModel):
    """List of aliases."""

    total: int
    items: list[CompanyAliasOut]


class CompanyAliasRemapIn(BaseModel):
    """Request body to remap an alias to a different canonical company."""

    company_id: int
