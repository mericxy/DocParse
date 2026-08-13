"""Single-table persistence model for transcription jobs and their JSON."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Transcription(Base):
    __tablename__ = "transcricoes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
