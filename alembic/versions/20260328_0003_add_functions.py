"""Add functions table with hybrid search support.

Revision ID: 20260328_0003
Revises: 20260328_0002
Create Date: 2026-03-28 00:00:00

"""

from __future__ import annotations

import alembic.op as op


revision = '20260328_0003'
down_revision = '20260328_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Functions table stores individual function/method definitions extracted
    # from indexed source files via tree-sitter.
    op.execute(
        """
        CREATE TABLE functions (
            id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            file_id     BIGINT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            project_id  BIGINT NOT NULL,
            name        TEXT   NOT NULL,
            signature   TEXT,
            start_line  INT    NOT NULL,
            end_line    INT    NOT NULL,
            body        TEXT   NOT NULL,
            checksum    TEXT   NOT NULL,
            summary     TEXT,
            embedding   vector,
            fts         tsvector GENERATED ALWAYS AS (
                            to_tsvector('english',
                                name || ' ' || coalesce(summary, '')
                            )
                        ) STORED,
            last_updated TIMESTAMPTZ,
            CONSTRAINT uq_functions_file_start_line UNIQUE (file_id, start_line)
        )
        """
    )

    op.execute('CREATE INDEX ix_functions_file_id    ON functions (file_id)')
    op.execute('CREATE INDEX ix_functions_project_id ON functions (project_id)')
    op.execute('CREATE INDEX ix_functions_fts        ON functions USING GIN (fts)')

    # hybrid_search_functions mirrors hybrid_search_files but operates on the
    # functions table, joining to files to surface the containing file path.
    #
    # RRF score = 1/(k + rank_semantic) + 1/(k + rank_keyword)
    #
    # Parameters:
    #   query_embedding  – pre-computed embedding of the search query
    #   query_text       – raw query string for full-text search
    #   p_project_id     – optional project filter (NULL = all projects)
    #   match_count      – number of results to return (default 10)
    #   rrf_k            – RRF constant (default 60)
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
    op.execute(
        'DROP FUNCTION IF EXISTS hybrid_search_functions(vector, text, bigint, int, int)'
    )
    op.execute('DROP TABLE IF EXISTS functions')
