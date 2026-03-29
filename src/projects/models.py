"""ORM model for the projects table."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from files.models import File


class Project(Base):
    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    git_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    language: Mapped[Optional[str]] = mapped_column(Text)
    default_branch: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[Optional[list]] = mapped_column(Vector)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    files: Mapped[list[File]] = relationship(
        back_populates='project', cascade='all, delete-orphan'
    )
