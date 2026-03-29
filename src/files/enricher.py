"""LLM enrichment (summary + embedding) for indexed source files."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Connection, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from llm import embed_text, summarize_file
from files.models import File, FileData


logger = logging.getLogger(__name__)


def enrich_stale_files(
    conn: Connection, project_id: int, file_data: dict[str, FileData]
) -> None:
    """
    Identify all files whose checksum has changed or that have no summary
    yet, then enrich each of them with an LLM-generated summary and
    embedding.
    """
    if not file_data:
        return

    paths = list(file_data.keys())
    now = datetime.now(timezone.utc)

    stored = conn.execute(
        select(File.path, File.checksum, File.summary).where(
            File.project_id == project_id,
            tuple_(File.project_id, File.path).in_([(project_id, p) for p in paths]),
        )
    ).fetchall()
    stored_by_path = {row.path: row for row in stored}

    stale_paths = [
        path
        for path in paths
        if stored_by_path.get(path) is None
        or stored_by_path[path].summary is None
        or stored_by_path[path].checksum != file_data[path].checksum
    ]
    logger.info('%d file(s) require embedding.', len(stale_paths))

    for path in stale_paths:
        _enrich_file(conn, project_id, path, file_data[path], now)

    logger.info('Enrichment complete.')


def _enrich_file(
    conn: Connection, project_id: int, path: str, fd: FileData, now: datetime
) -> None:
    """
    Generate a summary and embedding for a single file and persist both
    to the files table.
    """
    logger.info('Embedding %s …', path)
    summary = summarize_file(path, fd.content)
    embedding = embed_text(summary)
    conn.execute(
        insert(File)
        .values(
            project_id=project_id,
            path=path,
            checksum=fd.checksum,
            summary=summary,
            embedding=embedding,
            last_updated=now,
        )
        .on_conflict_do_update(
            constraint='uq_files_project_path',
            set_={
                'summary': summary,
                'embedding': embedding,
                'last_updated': now,
            },
        )
    )
    logger.info('Enriched %s.', path)
