"""ORM model for the files table and FileData value object."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from functions.models import Function
    from projects.models import Project


@dataclass
class FileData:
    """Holds the decoded content and SHA-256 checksum of a source file."""

    content: str
    checksum: str


class File(Base):
    __tablename__ = 'files'
    __table_args__ = (
        UniqueConstraint('project_id', 'path', name='uq_files_project_path'),
        Index('ix_files_project_id', 'project_id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[Optional[list]] = mapped_column(Vector)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates='files')

    functions: Mapped[list[Function]] = relationship(
        back_populates='file', cascade='all, delete-orphan'
    )
