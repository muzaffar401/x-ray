# Audit logging helper service for tracking security and lifecycle actions.
from typing import Optional
from sqlalchemy.orm import Session
from app.models import AuditLog

VALID_ACTIONS = {
    "created",
    "viewed",
    "edited",
    "approved",
    "pdf_exported",
    "login",
    "login_failed",
}


def log_action(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    report_id: Optional[int] = None,
    details: str = "",
) -> AuditLog:
    """Safely log an application event without storing patient info or report text."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid audit action '{action}'. Allowed: {sorted(VALID_ACTIONS)}")

    # Ensure details do not exceed maximum storage length
    safe_details = (details or "")[:255]

    entry = AuditLog(
        user_id=user_id,
        action=action,
        report_id=report_id,
        details=safe_details,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
