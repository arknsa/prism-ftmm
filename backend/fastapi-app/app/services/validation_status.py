"""Validation-status assignment service (P3.5).

Implements deterministic validation-status assignment per Artifact A6 §5 and D-047:

  assign_validation_status(program, university_matched) -> str

Design constraints (D-024, D-047, D-039, D-002):
- Deterministic: same inputs → same status every call.
- The pipeline NEVER auto-validates — the final `validated` transition is a
  **curator gate** exercised through the Phase 4 curator UI (P4.8, D-024).
- The pipeline produces `pending` (curator review required) or `rejected`
  (explicit non-match; retained for audit/anti-churn per D-047).
- Non-matches NEVER silently drop — they become `pending` or `rejected`.
- This function has no DB access; it is a pure deterministic function.

Decisions: D-024, D-047, D-039, Artifact A6 §5.
"""

from __future__ import annotations

from app.models.reference import StudyProgram

# ---------------------------------------------------------------------------
# Status constants (D-047)
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_VALIDATED = "validated"  # set only by curator (NOT by this service)
STATUS_REJECTED = "rejected"

_SENTINEL_PROGRAM_NAME = "Other / Unknown"


def assign_validation_status(
    program: StudyProgram,
    university_matched: bool,
) -> str:
    """Assign a validation_status candidate for a staged alumni row.

    Rules (Artifact A6 §5):
    | program.is_ftmm_valid | university_matched | Result    |
    |-----------------------|--------------------|-----------|
    | True                  | True               | pending   |
    | True                  | False              | pending   |
    | False                 | True               | pending   |
    | False                 | False              | rejected  |

    The `validated` state is NEVER assigned here — it requires the curator
    gate (D-024). This function only ever returns `pending` or `rejected`.

    Args:
        program: the StudyProgram instance returned by match_program().
        university_matched: result of is_unair() for the staged row.

    Returns:
        "pending" or "rejected" (never "validated").
    """
    is_valid_program = program.is_ftmm_valid

    if not is_valid_program and not university_matched:
        return STATUS_REJECTED

    return STATUS_PENDING
