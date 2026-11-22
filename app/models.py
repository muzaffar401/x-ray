# SQLAlchemy ORM database models for radiology reports, users, and audit logs.
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="doctor", nullable=False)  # "doctor" or "admin"
    is_active = Column(Boolean, default=True, nullable=False)


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

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(32), nullable=False)  # created, viewed, edited, approved, pdf_exported, login, login_failed
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    details = Column(String(255), nullable=True)
