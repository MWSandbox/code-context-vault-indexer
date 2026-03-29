"""Add hybrid search: fts column, GIN index, and hybrid_search_files function.

Revision ID: 20260328_0002
Revises: 20260328_0001
Create Date: 2026-03-28 00:00:00

"""

from __future__ import annotations

import alembic.op as op


revision = '20260328_0002'
down_revision = '20260328_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stored tsvector column combining path and summary for full-text search.
    # GENERATED ALWAYS AS ... STORED keeps it in sync automatically on writes.
    op.execute(
        """
        ALTER TABLE files
            ADD COLUMN fts tsvector
                GENERATED ALWAYS AS (
                    to_tsvector('english',
                        coalesce(path, '') || ' ' || coalesce(summary, '')
                    )
                ) STORED
        """
    )

    op.execute('CREATE INDEX ix_files_fts ON files USING GIN (fts)')

    # hybrid_search_files combines semantic (vector cosine distance) and
    # keyword (full-text) rankings via Reciprocal Rank Fusion (RRF).
    #
    # RRF score = 1/(k + rank_semantic) + 1/(k + rank_keyword)
    #
    # Parameters:
    #   query_embedding  – pre-computed embedding of the search query
    #   query_text       – raw query string for full-text search
    #   p_project_id     – optional project filter (NULL = all projects)
    #   match_count      – number of results to return (default 10)
    #   rrf_k            – RRF constant, higher = less weight on top ranks
    #                      (default 60, a widely used starting value)
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
                -- Rank candidates by cosine distance (ascending = more similar).
                -- match_count * 2 gives both branches enough candidates to merge.
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
                -- Rank candidates by full-text relevance (descending = more relevant).
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
                -- Full outer join so a result appearing in only one branch still
                -- contributes its partial RRF score.
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
    op.execute(
        'DROP FUNCTION IF EXISTS hybrid_search_files(vector, text, bigint, int, int)'
    )
    op.execute('DROP INDEX IF EXISTS ix_files_fts')
    op.execute('ALTER TABLE files DROP COLUMN IF EXISTS fts')
