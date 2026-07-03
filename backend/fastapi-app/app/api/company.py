"""Company and alias management endpoints (P4.6, P4.10 backend).

  GET    /api/v1/companies              — list all companies
  GET    /api/v1/companies/{id}         — get company by ID
  PATCH  /api/v1/companies/{id}         — update industry_id / location_id
  GET    /api/v1/companies/{id}/aliases — list aliases for a company
  GET    /api/v1/aliases/{id}           — get a single alias
  PATCH  /api/v1/aliases/{id}/remap     — remap alias to different company

Permission: company:read (read), company:write (write).
Audit: every mutation writes AUDIT_LOG (D-025).

Decisions: D-017, D-018, D-019, D-025, D-031.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.dependencies.rbac import require_permission
from app.models.company import Company, CompanyAlias
from app.schemas.auth import AuthenticatedUser
from app.schemas.company import (
    CompanyAliasListOut,
    CompanyAliasOut,
    CompanyAliasRemapIn,
    CompanyListOut,
    CompanyOut,
    CompanyUpdateIn,
)
from app.services.audit import write_audit_entry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["company"])


# ---------------------------------------------------------------------------
# GET /api/v1/companies
# ---------------------------------------------------------------------------


@router.get(
    "/companies",
    response_model=CompanyListOut,
    summary="List all canonical companies",
)
def list_companies(
    _user: AuthenticatedUser = Depends(require_permission("company:read")),
    session: Session = Depends(get_session),
) -> CompanyListOut:
    """Return all Company rows ordered by canonical_name.

    Permission required: ``company:read``.
    """
    companies = list(session.scalars(select(Company).order_by(Company.canonical_name)).all())
    return CompanyListOut(
        total=len(companies),
        items=[CompanyOut.model_validate(c) for c in companies],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/companies/{company_id}
# ---------------------------------------------------------------------------


@router.get(
    "/companies/{company_id}",
    response_model=CompanyOut,
    summary="Get a company by ID",
)
def get_company(
    company_id: int,
    _user: AuthenticatedUser = Depends(require_permission("company:read")),
    session: Session = Depends(get_session),
) -> CompanyOut:
    """Return a single Company by PK.

    Permission required: ``company:read``.
    """
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found.",
        )
    return CompanyOut.model_validate(company)


# ---------------------------------------------------------------------------
# PATCH /api/v1/companies/{company_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/companies/{company_id}",
    response_model=CompanyOut,
    summary="Update a company's industry and/or location assignment",
)
def update_company(
    company_id: int,
    body: CompanyUpdateIn,
    user: AuthenticatedUser = Depends(require_permission("company:write")),
    session: Session = Depends(get_session),
) -> CompanyOut:
    """Curator assigns industry_id and/or location_id to a company (D-018, D-019).

    Only the provided fields are updated; omitted fields are left unchanged.
    Writes an AUDIT_LOG entry (D-025).
    Permission required: ``company:write`` (Admin, Data Curator).
    """
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found.",
        )

    old_values: dict[str, object] = {
        "industry_id": company.industry_id,
        "location_id": company.location_id,
    }

    if body.industry_id is not None:
        company.industry_id = body.industry_id
    if body.location_id is not None:
        company.location_id = body.location_id

    new_values: dict[str, object] = {
        "industry_id": company.industry_id,
        "location_id": company.location_id,
    }

    write_audit_entry(
        session,
        table_name="company",
        record_id=str(company_id),
        action_type="UPDATE",
        old_values=old_values,
        new_values=new_values,
        changed_by=user.user_id,
    )

    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Unexpected error updating company %d", company_id)
        raise

    logger.info(
        "company updated: company_id=%d industry_id=%r location_id=%r actor=%d",
        company_id,
        company.industry_id,
        company.location_id,
        user.user_id,
    )
    return CompanyOut.model_validate(company)


# ---------------------------------------------------------------------------
# GET /api/v1/companies/{company_id}/aliases
# ---------------------------------------------------------------------------


@router.get(
    "/companies/{company_id}/aliases",
    response_model=CompanyAliasListOut,
    summary="List all aliases for a company",
)
def list_company_aliases(
    company_id: int,
    _user: AuthenticatedUser = Depends(require_permission("company:read")),
    session: Session = Depends(get_session),
) -> CompanyAliasListOut:
    """Return all CompanyAlias rows for a given company.

    Permission required: ``company:read``.
    """
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found.",
        )

    aliases = list(
        session.scalars(
            select(CompanyAlias)
            .where(CompanyAlias.company_id == company_id)
            .order_by(CompanyAlias.alias_name)
        ).all()
    )
    return CompanyAliasListOut(
        total=len(aliases),
        items=[CompanyAliasOut.model_validate(a) for a in aliases],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/aliases/{alias_id}
# ---------------------------------------------------------------------------


@router.get(
    "/aliases/{alias_id}",
    response_model=CompanyAliasOut,
    summary="Get a single company alias by ID",
)
def get_alias(
    alias_id: int,
    _user: AuthenticatedUser = Depends(require_permission("company:read")),
    session: Session = Depends(get_session),
) -> CompanyAliasOut:
    """Return a single CompanyAlias by PK.

    Permission required: ``company:read``.
    """
    alias = session.get(CompanyAlias, alias_id)
    if alias is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alias {alias_id} not found.",
        )
    return CompanyAliasOut.model_validate(alias)


# ---------------------------------------------------------------------------
# PATCH /api/v1/aliases/{alias_id}/remap
# ---------------------------------------------------------------------------


@router.patch(
    "/aliases/{alias_id}/remap",
    response_model=CompanyAliasOut,
    summary="Remap a company alias to a different canonical company",
)
def remap_alias(
    alias_id: int,
    body: CompanyAliasRemapIn,
    user: AuthenticatedUser = Depends(require_permission("company:write")),
    session: Session = Depends(get_session),
) -> CompanyAliasOut:
    """Curator remaps a raw employer alias to a different canonical company (D-017).

    This corrects cases where two differently-spelled names refer to the same company.
    Writes an AUDIT_LOG entry (D-025).
    Permission required: ``company:write`` (Admin, Data Curator).
    """
    alias = session.get(CompanyAlias, alias_id)
    if alias is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alias {alias_id} not found.",
        )

    # Verify target company exists
    target_company = session.get(Company, body.company_id)
    if target_company is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target company {body.company_id} not found.",
        )

    old_company_id = alias.company_id
    alias.company_id = body.company_id

    write_audit_entry(
        session,
        table_name="company_alias",
        record_id=str(alias_id),
        action_type="UPDATE",
        old_values={"company_id": old_company_id},
        new_values={"company_id": body.company_id},
        changed_by=user.user_id,
    )

    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Unexpected error remapping alias %d", alias_id)
        raise

    logger.info(
        "alias remapped: alias_id=%d old_company=%d new_company=%d actor=%d",
        alias_id,
        old_company_id,
        body.company_id,
        user.user_id,
    )
    return CompanyAliasOut.model_validate(alias)
