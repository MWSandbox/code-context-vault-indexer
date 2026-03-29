"""Indexing of source files for a registered project."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Connection
from sqlalchemy.dialects.postgresql import insert

from git import get_files_for_language
from files.models import File, FileData


logger = logging.getLogger(__name__)


def index_files(
    conn: Connection, project_id: int, language: str, repo_root: Path
) -> dict[str, FileData]:
    """
    Upsert a row in the files table for every git-tracked source file that
    belongs to the detected language. Only path and checksum are populated;
    summary and embedding are handled by a separate enrichment step.

    Re-running is safe: existing rows are updated in place using the
    (project_id, path) unique constraint as the conflict key.

    Returns a mapping of relative file path to FileData for further enrichment.
    """
    paths = get_files_for_language(language)
    logger.info('Found %d %s file(s) to index.', len(paths), language)
    if not paths:
        return {}

    now = datetime.now(timezone.utc)

    file_data: dict[str, FileData] = {}
    for path in paths:
        raw = (repo_root / path).read_bytes()
        file_data[path] = FileData(
            content=raw.decode('utf-8', errors='replace'),
            checksum=hashlib.sha256(raw).hexdigest(),
        )

    rows = [
        {
            'project_id': project_id,
            'path': path,
            'checksum': fd.checksum,
            'body': fd.content,
            'last_updated': now,
        }
        for path, fd in file_data.items()
    ]
    stmt = insert(File)
    stmt = stmt.on_conflict_do_update(
        constraint='uq_files_project_path',
        set_={
            'checksum': stmt.excluded.checksum,
            'body': stmt.excluded.body,
            'last_updated': stmt.excluded.last_updated,
        },
    )
    conn.execute(stmt, rows)
    logger.info('Upserted %d file(s).', len(rows))

    return file_data
