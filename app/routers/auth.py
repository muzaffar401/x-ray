# Authentication and authorization route handlers with brute-force protection.
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, UserRead
from app.security import COOKIE_NAME, create_access_token, get_current_user, verify_password
from app.services.audit import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory tracking of failed login attempts per username
FAILED_ATTEMPTS: Dict[str, List[float]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 60.0


def _check_rate_limit(username: str) -> None:
    now = time.time()
    attempts = FAILED_ATTEMPTS.get(username, [])
    # Retain attempts recorded within the last 60 seconds
    recent = [t for t in attempts if now - t < LOCKOUT_SECONDS]
    FAILED_ATTEMPTS[username] = recent

    if len(recent) >= MAX_FAILED_ATTEMPTS:
        remaining = int(LOCKOUT_SECONDS - (now - recent[0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Login temporarily locked for {max(1, remaining)} seconds.",
        )


def _record_failed_attempt(username: str) -> None:
    now = time.time()
    attempts = FAILED_ATTEMPTS.get(username, [])
    attempts.append(now)
    FAILED_ATTEMPTS[username] = [t for t in attempts if now - t < LOCKOUT_SECONDS]


def _clear_failed_attempts(username: str) -> None:
    FAILED_ATTEMPTS.pop(username, None)


@router.post("/login", response_model=UserRead)
def login(
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    username = login_data.username.strip()

    # 1. Check rate limit
    _check_rate_limit(username)

    # 2. Look up user
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        _record_failed_attempt(username)
        log_action(db, action="login_failed", user_id=user.id if user else None, details="Failed login attempt")
        # Check if this failure triggered lockout
        attempts = FAILED_ATTEMPTS.get(username, [])
        if len(attempts) >= MAX_FAILED_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Login temporarily locked for 1 minute.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not user.is_active:
        log_action(db, action="login_failed", user_id=user.id, details="Inactive user login attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    # 3. Successful login - clear failures and issue cookie
    _clear_failed_attempts(username)
    log_action(db, action="login", user_id=user.id, details="User logged in successfully")

    token = create_access_token(data={"sub": user.username, "user_id": user.id, "role": user.role})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )

    return user


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )
    return {"status": "ok"}


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
