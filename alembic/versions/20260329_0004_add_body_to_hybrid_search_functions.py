"""Return body column from hybrid_search_functions.

Revision ID: 20260329_0004
Revises: 20260328_0003
Create Date: 2026-03-29 00:00:00

"""

from __future__ import annotations

import alembic.op as op


revision = '20260329_0004'
down_revision = '20260328_0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        'DROP FUNCTION IF EXISTS hybrid_search_functions(vector, text, bigint, int, int)'
    )
    op.execute(
        """
        CREATE FUNCTION hybrid_search_functions(
            query_embedding  vector,
            query_text       text,
            p_project_id     bigint  DEFAULT NULL,
            match_count      int     DEFAULT 10,
            rrf_k            int     DEFAULT 60
        )
        RETURNS TABLE (
            id          bigint,
            file_id     bigint,
            project_id  bigint,
            path        text,
            name        text,
            summary     text,
            body        text,
            rrf_score   double precision
        )
        LANGUAGE sql
        STABLE
        AS $fn$
            WITH semantic AS (
                -- Rank candidates by cosine distance (ascending = more similar).
                SELECT
                    fn.id,
                    ROW_NUMBER() OVER (
                        ORDER BY fn.embedding <=> query_embedding
                    ) AS rank
                FROM functions fn
                WHERE (p_project_id IS NULL OR fn.project_id = p_project_id)
                  AND fn.embedding IS NOT NULL
                ORDER BY fn.embedding <=> query_embedding
                LIMIT match_count * 2
            ),
            keyword AS (
                -- Rank candidates by full-text relevance (descending = more relevant).
                SELECT
                    fn.id,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(
                            fn.fts,
                            websearch_to_tsquery('english', query_text)
                        ) DESC
                    ) AS rank
                FROM functions fn
                WHERE (p_project_id IS NULL OR fn.project_id = p_project_id)
                  AND fn.fts @@ websearch_to_tsquery('english', query_text)
                ORDER BY ts_rank_cd(
                    fn.fts,
                    websearch_to_tsquery('english', query_text)
                ) DESC
                LIMIT match_count * 2
            ),
            combined AS (
                -- Full outer join so a result appearing in only one branch still
                -- contributes its partial RRF score.
                SELECT
                    COALESCE(s.id, k.id)                             AS id,
                    COALESCE(1.0 / (rrf_k + s.rank), 0.0)
                    + COALESCE(1.0 / (rrf_k + k.rank), 0.0)         AS score
                FROM semantic s
                FULL OUTER JOIN keyword k ON s.id = k.id
            )
            SELECT
                fn.id,
                fn.file_id,
                fn.project_id,
                f.path,
                fn.name,
                fn.summary,
                fn.body,
                c.score AS rrf_score
            FROM combined c
            JOIN functions fn ON fn.id = c.id
            JOIN files     f  ON f.id  = fn.file_id
            ORDER BY c.score DESC
            LIMIT match_count
        $fn$
        """
    )


def downgrade() -> None:
    """Restore hybrid_search_functions without the body column."""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION hybrid_search_functions(
            query_embedding  vector,
            query_text       text,
            p_project_id     bigint  DEFAULT NULL,
            match_count      int     DEFAULT 10,
            rrf_k            int     DEFAULT 60
        )
        RETURNS TABLE (
            id          bigint,
            file_id     bigint,
            project_id  bigint,
            path        text,
            name        text,
            summary     text,
            rrf_score   double precision
        )
        LANGUAGE sql
        STABLE
        AS $fn$
            WITH semantic AS (
                SELECT
                    fn.id,
                    ROW_NUMBER() OVER (
                        ORDER BY fn.embedding <=> query_embedding
                    ) AS rank
                FROM functions fn
                WHERE (p_project_id IS NULL OR fn.project_id = p_project_id)
                  AND fn.embedding IS NOT NULL
                ORDER BY fn.embedding <=> query_embedding
                LIMIT match_count * 2
            ),
            keyword AS (
                SELECT
                    fn.id,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(
                            fn.fts,
                            websearch_to_tsquery('english', query_text)
                        ) DESC
                    ) AS rank
                FROM functions fn
                WHERE (p_project_id IS NULL OR fn.project_id = p_project_id)
                  AND fn.fts @@ websearch_to_tsquery('english', query_text)
                ORDER BY ts_rank_cd(
                    fn.fts,
                    websearch_to_tsquery('english', query_text)
                ) DESC
                LIMIT match_count * 2
            ),
            combined AS (
                SELECT
                    COALESCE(s.id, k.id)                             AS id,
                    COALESCE(1.0 / (rrf_k + s.rank), 0.0)
                    + COALESCE(1.0 / (rrf_k + k.rank), 0.0)         AS score
                FROM semantic s
                FULL OUTER JOIN keyword k ON s.id = k.id
            )
            SELECT
                fn.id,
                fn.file_id,
                fn.project_id,
                f.path,
                fn.name,
                fn.summary,
                c.score AS rrf_score
            FROM combined c
            JOIN functions fn ON fn.id = c.id
            JOIN files     f  ON f.id  = fn.file_id
            ORDER BY c.score DESC
            LIMIT match_count
        $fn$
        """
    )
