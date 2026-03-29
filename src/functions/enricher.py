"""LLM enrichment (summary + embedding) for indexed function definitions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Connection, select, update

from llm import embed_text, summarize_function
from files.models import File
from functions.models import Function


logger = logging.getLogger(__name__)


def enrich_stale_functions(conn: Connection, project_id: int) -> None:
    """
    Find all function rows for the given project that have no summary yet,
    then generate and persist an LLM summary and embedding for each of them.
    """
    stale = conn.execute(
        select(Function.id, Function.name, Function.body, File.path)
        .join(File, Function.file_id == File.id)
        .where(
            Function.project_id == project_id,
            Function.summary.is_(None),
        )
    ).fetchall()

    logger.info('%d function(s) require embedding.', len(stale))
    if not stale:
        return

    for row in stale:
        _enrich_function(conn, row.id, row.path, row.name, row.body)

    logger.info('Function enrichment complete.')


def _enrich_function(
    conn: Connection,
    function_id: int,
    path: str,
    name: str,
    body: str,
) -> None:
    """
    Generate a summary and embedding for a single function and persist both
    to the functions table.
    """
    logger.info('Embedding %s::%s …', path, name)
    summary = summarize_function(path, name, body)
    embedding = embed_text(summary)
    conn.execute(
        update(Function)
        .where(Function.id == function_id)
        .values(
            summary=summary,
            embedding=embedding,
            last_updated=datetime.now(timezone.utc),
        )
    )
    logger.info('Enriched %s::%s.', path, name)
