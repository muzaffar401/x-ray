# SQLAlchemy ORM database models for radiology reports.
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from app.db import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    image_path = Column(String(512), nullable=False)
    original_filename = Column(String(255), nullable=False)

    engine_name = Column(String(64), nullable=False)
    is_mock = Column(Boolean, default=True, nullable=False)

    ai_findings = Column(Text, nullable=False)
    ai_impression = Column(Text, nullable=False)

    final_findings = Column(Text, nullable=False)
    final_impression = Column(Text, nullable=False)

    status = Column(String(32), default="draft", nullable=False)  # "draft" or "approved"
    approved_at = Column(DateTime(timezone=True), nullable=True)
