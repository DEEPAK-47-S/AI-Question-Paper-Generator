from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user
from ..auth.security import create_access_token, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import ForgotPasswordRequest, LoginRequest, PasswordChange, TokenResponse
from ..services.audit import record_audit

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _public_user(user: User) -> dict:
    return {
        "id": user.id, "email": user.email, "username": user.username,
        "full_name": user.full_name, "role": user.role,
        "department_id": user.department_id, "must_change_password": user.must_change_password,
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    identifier = payload.username.strip().lower()
    user = db.query(User).filter(or_(User.email == identifier, User.username == identifier)).first()
    now = datetime.now(timezone.utc)
    if user and user.locked_until:
        locked = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
        if locked > now:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account temporarily locked after repeated attempts. Try again later.")
    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_login_attempts = 0
            record_audit(db, user, "auth.login_failed", "user", user.id, {"identifier": identifier}, request)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username/email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive. Contact an administrator.")
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    record_audit(db, user, "auth.login", "user", user.id, request=request)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role, user.auth_version), user=_public_user(user))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _public_user(user)


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.auth_version += 1  # Immediately invalidates all outstanding access tokens.
    record_audit(db, user, "auth.logout", "user", user.id)
    db.commit()
    return {"message": "Signed out successfully"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # Non-enumerating response. Production deployments connect this event to their approved mail service.
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user:
        record_audit(db, user, "auth.password_reset_requested", "user", user.id)
        db.commit()
    return {"message": "If an active account matches that email, the administrator will receive a reset request."}


@router.post("/change-password")
def change_password(payload: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.auth_version += 1
    record_audit(db, user, "auth.password_changed", "user", user.id)
    db.commit()
    return {"message": "Password changed. Please sign in again."}
