# Audit logging administrative API router.
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogRead
from app.security import get_current_user

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=List[AuditLogRead])
def get_audit_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AuditLog]:
    # Enforce admin-only access
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to access audit logs.",
        )

    # Return latest 200 audit log entries
    return (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(200)
        .all()
    )
