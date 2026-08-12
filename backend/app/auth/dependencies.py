"""FastAPI authorization dependencies and ownership helpers."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is unavailable")
    if payload.get("ver", 0) != user.auth_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been signed out")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission for this action")
        return user
    return dependency


def can_access_owner(user: User, owner_id: str) -> bool:
    return user.role in {"admin", "super_admin"} or user.id == owner_id


def enforce_owner(user: User, owner_id: str) -> None:
    if not can_access_owner(user, owner_id):
        # Do not reveal whether a private resource exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
