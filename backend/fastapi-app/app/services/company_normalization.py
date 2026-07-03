"""Company normalization service (P3.6).

Resolves a raw employer string from a staged row to a canonical COMPANY record
via the COMPANY_ALIAS table. On first sight of a new employer string, creates
both a canonical COMPANY and a COMPANY_ALIAS pointing to it.

Design:
- Deterministic: same raw_employer → same canonical_name every time (D-017, D-039).
- No fuzzy matching: exact alias lookup only. Curators correct aliases via Phase 4 (P4.10).
- industry_id and location_id are left NULL on first-sight creation — the curator assigns
  them later (D-018, D-019); Phase 3 does NOT auto-classify.
- source_id on the alias records which data source introduced it (D-046/D-049).
- All writes go through the caller's session; the caller owns commit (D-031 pattern).

Decisions: D-008, D-017, D-018, D-019, D-031, D-039, D-046, D-049.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyAlias


def _normalize_alias(raw: str) -> str:
    """Return a deterministic canonical form of a raw employer string.

    Steps:
    1. Strip leading/trailing whitespace.
    2. Collapse internal whitespace runs to a single space.
    3. Preserve original casing (canonical_name stores the first-seen form).

    The result is stored as the alias_name and forms the lookup key.
    """
    return re.sub(r"\s+", " ", raw.strip())


def resolve_company(
    raw_employer: str | None,
    source_id: int | None,
    session: Session,
) -> Company | None:
    """Resolve a raw employer string to a canonical Company.

    Returns None if ``raw_employer`` is blank/absent — an alumni record with no
    employer is valid (they simply have no career candidate for this import batch).

    Algorithm:
    1. Normalize the raw string (collapse whitespace).
    2. Lookup COMPANY_ALIAS by normalized alias_name.
    3. If found → return the linked Company.
    4. If not found → create Company (canonical_name = normalized raw) + CompanyAlias.
    5. Return the Company.

    The caller's session is used; the caller owns flush/commit.

    Args:
        raw_employer: raw employer name from the staged row (may be None/blank).
        source_id: FK to CAPTURE_SOURCE; recorded on the alias for provenance (D-046).
        session: active SQLAlchemy session.

    Returns:
        A Company instance (existing or new) or None if employer is absent.
    """
    if not raw_employer or not raw_employer.strip():
        return None

    normalized = _normalize_alias(raw_employer)

    # Check alias table first — the canonical lookup (D-017)
    alias = session.scalar(select(CompanyAlias).where(CompanyAlias.alias_name == normalized))
    if alias is not None:
        company = session.get(Company, alias.company_id)
        return company

    # First sight: create canonical Company + alias
    company = Company(
        canonical_name=normalized,
        industry_id=None,  # curator assigns in Phase 4 (P4.10)
        location_id=None,  # curator assigns in Phase 4
    )
    session.add(company)
    session.flush()  # obtain company_id for the FK

    alias = CompanyAlias(
        company_id=company.company_id,
        alias_name=normalized,
        source_id=source_id,
    )
    session.add(alias)

    return company
