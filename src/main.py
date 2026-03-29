"""Entry point: register the current git repository and index its source files."""

from __future__ import annotations

import logging
from pathlib import Path

from database import get_connection
from files.enricher import enrich_stale_files
from files.indexer import index_files
from functions.enricher import enrich_stale_functions
from functions.indexer import index_functions
from projects.indexer import register_project


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Register the current git repository as a project and index all source
    files belonging to its primary language.
    """
    with get_connection() as conn:
        project_id, language = register_project(conn)

        if language:
            file_data = index_files(conn, project_id, language, Path.cwd())
            enrich_stale_files(conn, project_id, file_data)
            index_functions(conn, project_id, file_data, language)
            enrich_stale_functions(conn, project_id)
        else:
            logger.warning('No primary language detected — skipping file indexing.')


if __name__ == '__main__':
    main()
