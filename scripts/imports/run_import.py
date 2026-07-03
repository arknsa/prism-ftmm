"""CLI entry point for the import pipeline (P3.3).

Runs the same parse_import service used by POST /api/v1/imports, writing
staging rows + an audit entry atomically. No request context is available,
so ``changed_by`` is always NULL (consistent with audit_log.changed_by
nullability, documented in ImportBatch.created_by).

Usage:
    DATABASE_URL=postgresql+psycopg://... \\
        uv run python scripts/imports/run_import.py \\
        --source "LinkedIn" --source-id 3 --file alumni.csv

Exit codes:
    0  success
    1  parse / validation error (bad file, unknown source)
    2  configuration / database error

Decisions: D-033 (manual import), D-025 (audit), D-031 (gateway parity).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure repo root is on the path so the script can import app/ and _utils.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "fastapi-app"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("run_import")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_import",
        description="Import a CSV/XLSX source file into the staging tables.",
    )
    parser.add_argument(
        "--source",
        required=True,
        metavar="SOURCE_TYPE",
        help='Source type: "LinkedIn", "Verified Faculty Record", or "Tracer Study".',
    )
    parser.add_argument(
        "--source-id",
        required=True,
        type=int,
        metavar="INT",
        dest="source_id",
        help="FK to CAPTURE_SOURCE.source_id.",
    )
    parser.add_argument(
        "--file",
        required=True,
        metavar="PATH",
        help="Path to the CSV or XLSX file to import.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Lazy imports after path setup — keeps startup fast for --help.
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from _utils import normalize_db_url  # type: ignore[import-not-found]
    except ImportError:
        # Running from backend/fastapi-app dir; _utils not needed (url already set).
        def normalize_db_url(url: str) -> str:  # type: ignore[misc]
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            if url.startswith("postgresql://") and "+psycopg" not in url:
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

    try:
        from app.services.audit import write_audit_entry
        from app.services.import_parser import parse_import
    except ModuleNotFoundError as exc:
        logger.error("Cannot import app package — make sure to run from repo root: %s", exc)
        sys.exit(2)

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set.")
        sys.exit(2)

    try:
        engine = create_engine(normalize_db_url(database_url), pool_pre_ping=True, future=True)
        Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    except Exception as exc:
        logger.error("Failed to create database engine: %s", exc)
        sys.exit(2)

    file_path = args.file
    try:
        with open(file_path, "rb") as fh:
            file_content = fh.read()
    except OSError as exc:
        logger.error("Cannot read file %r: %s", file_path, exc)
        sys.exit(1)

    filename = os.path.basename(file_path)

    session = Session()
    try:
        batch = parse_import(
            file_content=file_content,
            filename=filename,
            source_type=args.source,
            source_id=args.source_id,
            session=session,
            created_by=None,  # system/CLI context; no request actor
        )

        write_audit_entry(
            session,
            table_name="import_batch",
            record_id=str(batch.batch_id),
            action_type="INSERT",
            new_values={
                "batch_id": batch.batch_id,
                "source_id": batch.source_id,
                "filename": batch.filename,
                "total_rows": batch.total_rows,
                "parsed_rows": batch.parsed_rows,
                "error_rows": batch.error_rows,
                "status": batch.status,
                "created_by": None,
            },
            changed_by=None,
        )

        session.commit()

    except ValueError as exc:
        session.rollback()
        logger.error("Import failed — validation error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        session.rollback()
        logger.error("Import failed — unexpected error: %s", exc)
        sys.exit(2)
    finally:
        session.close()

    print(
        f"Import complete.\n"
        f"  batch_id   : {batch.batch_id}\n"
        f"  source     : {args.source}\n"
        f"  filename   : {filename}\n"
        f"  total_rows : {batch.total_rows}\n"
        f"  parsed_rows: {batch.parsed_rows}\n"
        f"  error_rows : {batch.error_rows}\n"
        f"  status     : {batch.status}"
    )


if __name__ == "__main__":
    main()
