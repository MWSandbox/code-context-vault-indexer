"""Indexing of function definitions extracted via tree-sitter."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Connection, delete, select
from sqlalchemy.dialects.postgresql import insert

from files.models import File, FileData
from functions.extractor import extract_functions
from functions.models import Function


logger = logging.getLogger(__name__)

_SUPPORTED_LANGUAGES = {'Python', 'JavaScript', 'TypeScript'}


def index_functions(
    conn: Connection,
    project_id: int,
    file_data: dict[str, FileData],
    language: str,
) -> None:
    """
    Extract function definitions from every file in file_data and upsert
    them into the functions table.

    Change detection is performed at the function level using body checksums:
    - New functions are inserted (summary/embedding left NULL for enrichment).
    - Functions whose body changed are updated; their summary and embedding are
      cleared so they will be re-enriched on the next run.
    - Functions that no longer appear in the file are deleted.
    - Unchanged functions (same checksum) are skipped completely, preserving
      any existing summary and embedding.

    Files whose language is not in {Python, JavaScript, TypeScript} are skipped.
    """
    if language not in _SUPPORTED_LANGUAGES or not file_data:
        return

    # Resolve path → file_id for every file we are about to process.
    file_rows = conn.execute(
        select(File.id, File.path).where(
            File.project_id == project_id,
            File.path.in_(list(file_data.keys())),
        )
    ).fetchall()
    file_id_by_path = {row.path: row.id for row in file_rows}

    now = datetime.now(timezone.utc)
    total_upserted = 0
    total_deleted = 0

    for path, fd in file_data.items():
        file_id = file_id_by_path.get(path)
        if file_id is None:
            continue

        extracted = extract_functions(path, fd.content, language)

        # Load existing functions for this file to drive delta logic.
        existing_rows = conn.execute(
            select(Function.start_line, Function.checksum).where(
                Function.file_id == file_id
            )
        ).fetchall()
        existing_by_line: dict[int, str] = {
            row.start_line: row.checksum for row in existing_rows
        }

        extracted_lines = {fn.start_line for fn in extracted}

        # Remove functions that no longer exist in the current file.
        removed = set(existing_by_line) - extracted_lines
        if removed:
            conn.execute(
                delete(Function).where(
                    Function.file_id == file_id,
                    Function.start_line.in_(removed),
                )
            )
            total_deleted += len(removed)

        # Upsert new or changed functions; skip unchanged ones.
        for fn in extracted:
            if existing_by_line.get(fn.start_line) == fn.checksum:
                continue  # unchanged — preserve existing summary and embedding

            values: dict = {
                'file_id': file_id,
                'project_id': project_id,
                'name': fn.name,
                'signature': fn.signature,
                'start_line': fn.start_line,
                'end_line': fn.end_line,
                'body': fn.body,
                'checksum': fn.checksum,
                'last_updated': now,
            }
            update_set: dict = {
                'name': fn.name,
                'signature': fn.signature,
                'end_line': fn.end_line,
                'body': fn.body,
                'checksum': fn.checksum,
                'last_updated': now,
            }

            if fn.start_line in existing_by_line:
                # Body changed — clear stale AI-generated content.
                values['summary'] = None
                values['embedding'] = None
                update_set['summary'] = None
                update_set['embedding'] = None

            conn.execute(
                insert(Function)
                .values(**values)
                .on_conflict_do_update(
                    constraint='uq_functions_file_start_line',
                    set_=update_set,
                )
            )
            total_upserted += 1

    logger.info(
        'Functions: %d upserted, %d deleted across %d file(s).',
        total_upserted,
        total_deleted,
        len(file_id_by_path),
    )
