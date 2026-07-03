"""Industry classification service (P3.7).

Attaches an industry classification to a Company record by looking up the
INDUSTRY table by exact industry_name. This is called only when the caller
has a deterministic industry string (e.g. from a Tracer Study "industry"
column) — it is NOT called speculatively.

Design constraints (D-018, D-042):
- Industry is attached at the COMPANY level, never per career/staging row.
- Only seeded industry rows are matched; no new Industry rows are created here.
  Curator assigns new industries via Phase 4 (P4.10).
- If the raw_industry string does not match any seeded industry_name exactly,
  the company.industry_id is left NULL. The curator classifies later.
- No fuzzy matching, no inference (D-039).
- All writes go through the caller's session; caller owns commit (D-031 pattern).

Decisions: D-018, D-031, D-039, D-042.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.reference import Industry

logger = logging.getLogger(__name__)


def attach_industry(
    company: Company,
    raw_industry: str | None,
    session: Session,
) -> None:
    """Set company.industry_id from a raw industry string.

    Performs an exact match against INDUSTRY.industry_name. If the string is
    absent or does not match any seeded row, company.industry_id is left
    unchanged (remains NULL on first-sight companies).

    Args:
        company: the Company instance to classify (may already have industry_id set).
        raw_industry: raw industry string from the staged row; may be None/blank.
        session: active SQLAlchemy session — changes are unflushed; caller commits.
    """
    if company.industry_id is not None:
        # Already classified — do not overwrite a curator-assigned classification.
        return

    if not raw_industry or not raw_industry.strip():
        return

    normalized = raw_industry.strip()

    industry = session.scalar(select(Industry).where(Industry.industry_name == normalized))
    if industry is None:
        logger.debug(
            "industry_classification: no exact match for %r — leaving NULL (curator assigns)",
            normalized,
        )
        return

    company.industry_id = industry.industry_id
