"""Password and JWT primitives. Password material is never logged."""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(user_id: str, role: str, auth_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "ver": auth_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "iss": "niet-ai-qpg",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM], issuer="niet-ai-qpg")
    except JWTError as exc:
        raise ValueError("Invalid or expired authentication token") from exc
