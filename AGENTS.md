# Project Scope
This is a project to index and embed source code into a pgvector database. The goal is to use those embeddings later with github copilot to search for specific information with a hybrid search.

# Data Model

Two tables, stored in PostgreSQL with the pgvector extension:

**`projects`** — represents a source code repository:
- `id` — BIGINT primary key
- `name` — display name
- `git_url` — unique repository URL
- `language` — primary programming language
- `default_branch` — e.g. `main`
- `summary` — LLM-generated description of the project
- `embedding` — pgvector embedding of the summary
- `last_updated` — timestamp of last indexing run

**`files`** — represents a single file within a project (1:N from projects):
- `id` — BIGINT primary key
- `project_id` — FK → `projects.id` (cascade delete)
- `path` — relative file path within the repository
- `checksum` — used to detect file changes between indexing runs
- `summary` — LLM-generated description of the file
- `embedding` — pgvector embedding of the summary
- `last_updated` — timestamp of last indexing run

# Registering a Project

Run `src/register_project.py` from inside any git repository to upsert it into the `projects` table:

```bash
python src/register_project.py
# or with a custom database URL:
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db python src/register_project.py
```

The script reads `name`, `git_url`, and `default_branch` from the local git repo (via `src/git.py`) and inserts or updates the matching row using `git_url` as the conflict key. `DATABASE_URL` defaults to the same connection string used by Alembic.

# Coding Style
- For functions use comments to explain its purpose with triple quote style