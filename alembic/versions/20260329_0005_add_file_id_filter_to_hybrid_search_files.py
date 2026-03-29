"""Add optional file_id filter to hybrid_search_files function.

Revision ID: 20260329_0005
Revises: 20260329_0004
Create Date: 2026-03-29 00:00:00

"""

from __future__ import annotations

import alembic.op as op


revision = '20260329_0005'
down_revision = '20260329_0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old signature before replacing with the new one that adds p_file_id.
    op.execute(
        'DROP FUNCTION IF EXISTS hybrid_search_files(vector, text, bigint, int, int)'
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION hybrid_search_files(
            query_embedding  vector,
            query_text       text,
            p_project_id     bigint  DEFAULT NULL,
            match_count      int     DEFAULT 10,
            rrf_k            int     DEFAULT 60,
            p_file_id        bigint  DEFAULT NULL
        )
        RETURNS TABLE (
            id          bigint,
            project_id  bigint,
            path        text,
            summary     text,
            rrf_score   double precision
        )
        LANGUAGE sql
        STABLE
        AS $fn$
            WITH semantic AS (
                SELECT
                    f.id,
                    ROW_NUMBER() OVER (
                        ORDER BY f.embedding <=> query_embedding
                    ) AS rank
                FROM files f
                WHERE (p_project_id IS NULL OR f.project_id = p_project_id)
                  AND (p_file_id    IS NULL OR f.id          = p_file_id)
                  AND f.embedding IS NOT NULL
                ORDER BY f.embedding <=> query_embedding
                LIMIT match_count * 2
            ),
            keyword AS (
                SELECT
                    f.id,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(
                            f.fts,
                            websearch_to_tsquery('english', query_text)
                        ) DESC
                    ) AS rank
                FROM files f
                WHERE (p_project_id IS NULL OR f.project_id = p_project_id)
                  AND (p_file_id    IS NULL OR f.id          = p_file_id)
                  AND f.fts @@ websearch_to_tsquery('english', query_text)
                ORDER BY ts_rank_cd(
                    f.fts,
                    websearch_to_tsquery('english', query_text)
                ) DESC
                LIMIT match_count * 2
            ),
            combined AS (
                SELECT
                    COALESCE(s.id, k.id)                                  AS id,
                    COALESCE(1.0 / (rrf_k + s.rank), 0.0)
                    + COALESCE(1.0 / (rrf_k + k.rank), 0.0)              AS score
                FROM semantic s
                FULL OUTER JOIN keyword k ON s.id = k.id
            )
            SELECT
                f.id,
                f.project_id,
                f.path,
                f.summary,
                c.score AS rrf_score
            FROM combined c
            JOIN files f ON f.id = c.id
            ORDER BY c.score DESC
            LIMIT match_count
        $fn$
        """
    )


def downgrade() -> None:
    # Restore original signature without p_file_id.
    op.execute(
        'DROP FUNCTION IF EXISTS hybrid_search_files(vector, text, bigint, int, int, bigint)'
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION hybrid_search_files(
            query_embedding  vector,
            query_text       text,
            p_project_id     bigint  DEFAULT NULL,
            match_count      int     DEFAULT 10,
            rrf_k            int     DEFAULT 60
        )
        RETURNS TABLE (
            id          bigint,
            project_id  bigint,
            path        text,
            summary     text,
            rrf_score   double precision
        )
        LANGUAGE sql
        STABLE
        AS $fn$
            WITH semantic AS (
                SELECT
                    f.id,
                    ROW_NUMBER() OVER (
                        ORDER BY f.embedding <=> query_embedding
                    ) AS rank
                FROM files f
                WHERE (p_project_id IS NULL OR f.project_id = p_project_id)
                  AND f.embedding IS NOT NULL
                ORDER BY f.embedding <=> query_embedding
                LIMIT match_count * 2
            ),
            keyword AS (
                SELECT
                    f.id,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(
                            f.fts,
                            websearch_to_tsquery('english', query_text)
                        ) DESC
                    ) AS rank
                FROM files f
                WHERE (p_project_id IS NULL OR f.project_id = p_project_id)
                  AND f.fts @@ websearch_to_tsquery('english', query_text)
                ORDER BY ts_rank_cd(
                    f.fts,
                    websearch_to_tsquery('english', query_text)
                ) DESC
                LIMIT match_count * 2
            ),
            combined AS (
                SELECT
                    COALESCE(s.id, k.id)                                  AS id,
                    COALESCE(1.0 / (rrf_k + s.rank), 0.0)
                    + COALESCE(1.0 / (rrf_k + k.rank), 0.0)              AS score
                FROM semantic s
                FULL OUTER JOIN keyword k ON s.id = k.id
            )
            SELECT
                f.id,
                f.project_id,
                f.path,
                f.summary,
                c.score AS rrf_score
            FROM combined c
            JOIN files f ON f.id = c.id
            ORDER BY c.score DESC
            LIMIT match_count
        $fn$
        """
    )
