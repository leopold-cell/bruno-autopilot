from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Keyword(Base):
    """A problem-based search query the autopilot intends to write an article for."""

    __tablename__ = "keywords"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    keyword: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(40))  # Anxiety|Depression|CBT|Sleep|Self-check
    intent: Mapped[str | None] = mapped_column(String(80), nullable=True)
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)  # the user pain behind the query
    priority: Mapped[int] = mapped_column(Integer, default=50)  # higher = sooner
    # queued | published | failed | skipped
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    slug: Mapped[str | None] = mapped_column(String(200), nullable=True)  # filled once published
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="ideation")  # ideation | autocomplete | gsc
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
