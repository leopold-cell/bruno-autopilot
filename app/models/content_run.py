from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContentRun(Base):
    """Audit log of one article generation attempt."""

    __tablename__ = "content_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    keyword_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    keyword: Mapped[str | None] = mapped_column(String(300), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # success | failed_generation | failed_qa | failed_publish
    status: Mapped[str] = mapped_column(String(30))
    qa_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    qa_issues: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
