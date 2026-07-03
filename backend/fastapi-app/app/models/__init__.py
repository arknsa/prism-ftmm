"""SQLAlchemy model registry.

Importing this package ensures all mapped classes are registered on Base.metadata
before Alembic's ``target_metadata`` is evaluated. Add each new model module here
as phases introduce new tables.
"""

from __future__ import annotations

from app.models.alumni import Alumni, ValidationStatus
from app.models.audit import AuditLog
from app.models.career import CareerRecord
from app.models.company import Company, CompanyAlias
from app.models.dedup import DedupCandidate
from app.models.reference import CaptureSource, Industry, Location, StudyProgram
from app.models.security import AppUser, Permission, Role, RolePermission
from app.models.snapshot import RefreshSnapshot
from app.models.staging import ImportBatch, StagingRow

__all__ = [
    # alumni
    "Alumni",
    "ValidationStatus",
    # audit
    "AuditLog",
    # career
    "CareerRecord",
    # company
    "Company",
    "CompanyAlias",
    # dedup (Phase 4)
    "DedupCandidate",
    # reference
    "CaptureSource",
    "Industry",
    "Location",
    "StudyProgram",
    # security
    "AppUser",
    "Permission",
    "Role",
    "RolePermission",
    # snapshot
    "RefreshSnapshot",
    # staging (Phase 3)
    "ImportBatch",
    "StagingRow",
]
