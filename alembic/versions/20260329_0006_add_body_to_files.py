"""Add body column to files table to store raw file content.

Revision ID: 20260329_0006
Revises: 20260329_0005
Create Date: 2026-03-29 00:00:00

"""

from __future__ import annotations

import alembic.op as op
import sqlalchemy as sa


revision = '20260329_0006'
down_revision = '20260329_0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('files', sa.Column('body', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('files', 'body')
