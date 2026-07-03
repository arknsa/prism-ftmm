"""Commit/storage stage (P4.5).

Orchestrates the full pipeline from a StagingRow to persistent Alumni + CareerRecord rows,
tagged with snapshot_id and source_id.

Public interface:

  commit_staging_row(row, snapshot_id, source_id, actor_id, session)
      → CommitResult

  commit_batch(batch_id, snapshot_id, actor_id, session)
      → list[CommitResult]

Pipeline per row (D-020, D-024, D-031, D-044, D-045, D-047):

  1. Skip rows with row_status != "pending" (already errored out in parsing).
  2. Normalize: match_program, resolve_company, clean_role_title,
               classify_seniority, is_unair, assign_validation_status.
  3. Dedup Tier 1: find_by_linkedin_url → auto-link if exact URL match.
  4. Dedup Tier 2 (when no Tier-1 match):
       - find_candidates_by_key → if matches found, check DedupCandidate resolutions.
       - Any pending resolution → skip row (needs curator action first).
       - All "merge" → use the merge-target alumni_id.
       - All "keep_separate" → create new Alumni.
       - No Tier-2 matches → create new Alumni.
  5. Create or update Alumni row.
  6. If company resolved: enforce D-020 (clear old is_current), create CareerRecord.
  7. Write audit entries for Alumni INSERT/UPDATE and CareerRecord INSERT.
  8. No commit here — caller owns transaction (D-031).

Decisions: D-020, D-024, D-031, D-039, D-044, D-045, D-047.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alumni import Alumni, ValidationStatus
from app.models.career import CareerRecord
from app.models.staging import ImportBatch, StagingRow
from app.services.audit import write_audit_entry
from app.services.company_normalization import resolve_company
from app.services.dedup import find_by_linkedin_url, find_candidates_by_key
from app.services.dedup_queue import enqueue_candidate
from app.services.program_matcher import is_unair, match_program
from app.services.role_seniority import classify_seniority, clean_role_title
from app.services.validation_status import assign_validation_status

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class CommitOutcome(StrEnum):
    """Outcome for a single row's commit attempt."""

    created = "created"
    linked = "linked"
    pending_dedup = "pending_dedup"
    skipped_error = "skipped_error"
    skipped_no_employer = "skipped_no_employer"


@dataclass
class CommitResult:
    """Result of attempting to commit a single StagingRow."""

    staging_row_id: int
    outcome: CommitOutcome
    alumni_id: int | None = None
    career_record_id: int | None = None
    detail: str = ""
    dedup_candidate_ids: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# D-020: enforce exactly one is_current per alumni
# ---------------------------------------------------------------------------


def _clear_current_career(alumni_id: int, session: Session) -> None:
    """Set is_current=False on any existing CareerRecord with is_current=True for this alumni.

    Called before inserting a new is_current=True record to maintain D-020 invariant
    (partial unique index: at most one is_current per alumni).
    """
    existing = session.scalar(
        select(CareerRecord).where(
            CareerRecord.alumni_id == alumni_id,
            CareerRecord.is_current == True,  # noqa: E712
        )
    )
    if existing is not None:
        existing.is_current = False


# ---------------------------------------------------------------------------
# Tier-2 dedup resolution helper
# ---------------------------------------------------------------------------


def _resolve_tier2(
    row: StagingRow,
    tier2_matches: list[Alumni],
    session: Session,
) -> tuple[Alumni | None, list[int], bool]:
    """Return (alumni_to_use, dedup_candidate_ids, needs_curator_action).

    For each Tier-2 match:
    - If all resolved as "merge": use the matched alumni (first merge target wins).
    - If any pending: enqueue and return needs_curator_action=True.
    - If all "keep_separate": create new alumni (caller handles creation).

    Returns:
        (alumni | None, candidate_ids, needs_curator_action)
        - alumni: the merge-target alumni if resolution is "merge"; else None.
        - candidate_ids: IDs of all DedupCandidate rows involved.
        - needs_curator_action: True if any candidates are pending.
    """
    from app.models.dedup import DedupCandidate

    candidate_ids: list[int] = []
    merge_target: Alumni | None = None
    any_pending = False

    for match in tier2_matches:
        # Check existing resolution for this (row, match) pair
        existing = session.scalar(
            select(DedupCandidate).where(
                DedupCandidate.staging_row_id == row.staging_row_id,
                DedupCandidate.matched_alumni_id == match.alumni_id,
            )
        )
        if existing is None:
            # No resolution yet — enqueue for curator review
            candidate = enqueue_candidate(row.staging_row_id, match.alumni_id, session)
            # Flush to get ID (we're still in caller's transaction)
            session.flush()
            candidate_ids.append(candidate.dedup_candidate_id)
            any_pending = True
        elif existing.resolution == "pending":
            candidate_ids.append(existing.dedup_candidate_id)
            any_pending = True
        elif existing.resolution == "merge":
            candidate_ids.append(existing.dedup_candidate_id)
            if merge_target is None:
                merge_target = match
        else:
            # keep_separate — skip this match, allow new alumni creation
            candidate_ids.append(existing.dedup_candidate_id)

    if any_pending:
        return None, candidate_ids, True

    return merge_target, candidate_ids, False


# ---------------------------------------------------------------------------
# Core commit function
# ---------------------------------------------------------------------------


def commit_staging_row(
    row: StagingRow,
    snapshot_id: int,
    source_id: int,
    actor_id: int | None,
    session: Session,
) -> CommitResult:
    """Process one StagingRow through the full normalization + storage pipeline.

    This function adds Alumni and CareerRecord rows to the session but does NOT
    flush or commit — the caller owns the transaction boundary (D-031).

    Args:
        row: The StagingRow to process. Must have row_status="pending" to proceed.
        snapshot_id: FK to the RefreshSnapshot this commit belongs to (D-021).
        source_id: FK to the CaptureSource for provenance (D-046).
        actor_id: AppUser.user_id of the curator triggering the commit; None for system.
        session: active SQLAlchemy session — caller owns commit.

    Returns:
        CommitResult describing the outcome for this row.
    """
    rid = row.staging_row_id

    # Step 1: skip error rows
    if row.row_status != "pending":
        return CommitResult(
            staging_row_id=rid,
            outcome=CommitOutcome.skipped_error,
            detail=f"row_status={row.row_status!r}; skipped.",
        )

    # Step 2: normalize
    program = match_program(row.raw_study_program, session)
    # StagingRow has no raw_university field (spec A1). Pass None → is_unair=False.
    # assign_validation_status then uses only program.is_ftmm_valid to gate rejection.
    university_matched = is_unair(None)
    validation_status = assign_validation_status(program, university_matched)
    role_title = clean_role_title(row.raw_role_title)
    seniority = classify_seniority(row.raw_role_title)
    company = resolve_company(row.raw_employer, source_id, session)

    # Step 3: Tier-1 dedup — exact linkedin_url match
    tier1_match = find_by_linkedin_url(row.raw_linkedin_url, session)

    alumni: Alumni | None = None
    outcome = CommitOutcome.created
    dedup_candidate_ids: list[int] = []

    if tier1_match is not None:
        # Tier-1 auto-link: staged row belongs to this existing alumni
        alumni = tier1_match
        outcome = CommitOutcome.linked
        # Update validation_status only if the existing row would be improved
        # (never downgrade from validated → pending; D-024 curator gate)
        if alumni.validation_status == ValidationStatus.pending and validation_status == "rejected":
            alumni.validation_status = ValidationStatus.rejected

    else:
        # Step 4: Tier-2 dedup — candidate key match
        tier2_matches = find_candidates_by_key(
            row.raw_full_name,
            program.program_id,
            row.raw_graduation_year,
            session,
        )

        if tier2_matches:
            merge_target, dedup_candidate_ids, needs_curator = _resolve_tier2(
                row, tier2_matches, session
            )
            if needs_curator:
                return CommitResult(
                    staging_row_id=rid,
                    outcome=CommitOutcome.pending_dedup,
                    detail="Tier-2 match(es) pending curator resolution.",
                    dedup_candidate_ids=dedup_candidate_ids,
                )
            if merge_target is not None:
                alumni = merge_target
                outcome = CommitOutcome.linked
            # else: all "keep_separate" → fall through to create new alumni

        if alumni is None:
            # Step 5: create new Alumni row (D-047: initial status = pending or rejected)
            alumni = Alumni(
                full_name=row.raw_full_name or "",
                university="Universitas Airlangga",
                study_program_id=program.program_id,
                graduation_year=row.raw_graduation_year or 0,
                linkedin_url=_normalize_linkedin_url_for_storage(row.raw_linkedin_url),
                validation_status=ValidationStatus(validation_status),
                source_id=source_id,
            )
            session.add(alumni)
            session.flush()  # obtain alumni_id for FK

            write_audit_entry(
                session,
                table_name="alumni",
                record_id=str(alumni.alumni_id),
                action_type="INSERT",
                new_values=_alumni_snapshot(alumni),
                changed_by=actor_id,
            )
            outcome = CommitOutcome.created

    # Step 6: create CareerRecord if company resolved
    if company is None:
        no_employer_outcome = (
            CommitOutcome.skipped_no_employer if outcome == CommitOutcome.created else outcome
        )
        return CommitResult(
            staging_row_id=rid,
            outcome=no_employer_outcome,
            alumni_id=alumni.alumni_id if alumni else None,
            detail="No employer; Alumni created but no CareerRecord written.",
            dedup_candidate_ids=dedup_candidate_ids,
        )

    if not role_title:
        role_title = "Unknown Role"

    # D-020: clear any existing is_current for this alumni before inserting new one
    _clear_current_career(alumni.alumni_id, session)

    career = CareerRecord(
        alumni_id=alumni.alumni_id,
        company_id=company.company_id,
        role_title=role_title,
        seniority=seniority,
        is_current=True,
        snapshot_id=snapshot_id,
        source_id=source_id,
        captured_on=datetime.date.today(),
    )
    session.add(career)
    session.flush()  # obtain career_record_id for audit

    write_audit_entry(
        session,
        table_name="career_record",
        record_id=str(career.career_record_id),
        action_type="INSERT",
        new_values=_career_snapshot(career),
        changed_by=actor_id,
    )

    return CommitResult(
        staging_row_id=rid,
        outcome=outcome,
        alumni_id=alumni.alumni_id,
        career_record_id=career.career_record_id,
        dedup_candidate_ids=dedup_candidate_ids,
    )


# ---------------------------------------------------------------------------
# Batch commit
# ---------------------------------------------------------------------------


def commit_batch(
    batch_id: int,
    snapshot_id: int,
    actor_id: int | None,
    session: Session,
) -> list[CommitResult]:
    """Process all pending StagingRows in an ImportBatch through the commit pipeline.

    Iterates over all StagingRows with row_status="pending" belonging to batch_id.
    Each row is committed via commit_staging_row. The caller owns commit — call
    session.commit() after this returns to persist all results atomically.

    Args:
        batch_id: FK to the ImportBatch to commit.
        snapshot_id: FK to the RefreshSnapshot for this commit run.
        actor_id: AppUser.user_id of the curator triggering the commit.
        session: active SQLAlchemy session — caller owns commit.

    Returns:
        List of CommitResult, one per StagingRow processed.
    """
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise ValueError(f"ImportBatch {batch_id} not found.")

    rows = list(session.scalars(select(StagingRow).where(StagingRow.batch_id == batch_id)).all())

    source_id = batch.source_id
    results: list[CommitResult] = []
    for row in rows:
        result = commit_staging_row(row, snapshot_id, source_id, actor_id, session)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_linkedin_url_for_storage(raw: str | None) -> str | None:
    """Return a normalized linkedin_url for storage, or None if absent."""
    if not raw or not raw.strip():
        return None
    return raw.strip().lower().rstrip("/")


def _alumni_snapshot(a: Alumni) -> dict[str, Any]:
    """Extract relevant Alumni fields as a dict for audit log."""
    return {
        "full_name": a.full_name,
        "study_program_id": a.study_program_id,
        "graduation_year": a.graduation_year,
        "university": a.university,
        "linkedin_url": a.linkedin_url,
        "validation_status": str(a.validation_status),
        "source_id": a.source_id,
    }


def _career_snapshot(c: CareerRecord) -> dict[str, Any]:
    """Extract relevant CareerRecord fields as a dict for audit log."""
    return {
        "alumni_id": c.alumni_id,
        "company_id": c.company_id,
        "role_title": c.role_title,
        "seniority": c.seniority,
        "is_current": c.is_current,
        "snapshot_id": c.snapshot_id,
        "source_id": c.source_id,
    }
