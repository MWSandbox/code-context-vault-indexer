"""Register the current git repository as a project in the database."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Connection
from sqlalchemy.dialects.postgresql import insert

from git import get_default_branch, get_git_url, get_primary_language, get_repo_name
from projects.models import Project


logger = logging.getLogger(__name__)


def register_project(conn: Connection) -> tuple[int, str | None]:
    """
    Extract git metadata from the current repository and upsert a row in the
    projects table. Re-running is safe: an existing row is updated in place
    using the git_url as the conflict key.

    Returns the project id and primary language.
    """
    git_url = get_git_url()
    name = get_repo_name(git_url)
    default_branch = get_default_branch()
    language = get_primary_language()

    logger.info('Name:           %s', name)
    logger.info('Git URL:        %s', git_url)
    logger.info('Default branch: %s', default_branch)
    logger.info('Language:       %s', language)

    stmt = (
        insert(Project)
        .values(
            name=name,
            git_url=git_url,
            default_branch=default_branch,
            language=language,
            last_updated=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=[Project.git_url],
            set_={
                'name': name,
                'default_branch': default_branch,
                'language': language,
                'last_updated': datetime.now(timezone.utc),
            },
        )
        .returning(Project.id)
    )
    row = conn.execute(stmt).fetchone()
    project_id: int = row[0]  # type: ignore[index]
    logger.info('Project registered successfully (id=%d).', project_id)

    return project_id, language
