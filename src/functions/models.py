"""ORM model for the functions table and FunctionDef value object."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from files.models import File


@dataclass
class FunctionDef:
    """Represents a single extracted function or method definition."""

    name: str
    signature: str
    start_line: int
    end_line: int
    body: str
    checksum: str


class Function(Base):
    __tablename__ = 'functions'
    __table_args__ = (
        UniqueConstraint('file_id', 'start_line', name='uq_functions_file_start_line'),
        Index('ix_functions_file_id', 'file_id'),
        Index('ix_functions_project_id', 'project_id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('files.id', ondelete='CASCADE'), nullable=False
    )
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[Optional[str]] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[Optional[list]] = mapped_column(Vector)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    file: Mapped[File] = relationship(back_populates='functions')
