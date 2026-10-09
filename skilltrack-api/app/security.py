from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import ACCESS_TOKEN_MINUTES, ALGORITHM, REFRESH_TOKEN_MINUTES, SECRET_KEY


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _encode(claims: dict, expires: datetime) -> str:
    return jwt.encode({**claims, "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int, role: str, not_after: datetime | None = None) -> str:
    """Short-lived token sent with every request. `not_after` keeps it from outliving the refresh token."""
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    if not_after is not None:
        expires = min(expires, not_after)
    return _encode({"sub": str(user_id), "role": role, "type": "access"}, expires)


def create_refresh_token(user_id: int) -> str:
    """Longer-lived token that can only be swapped for new access tokens (POST /auth/refresh)."""
    expires = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_MINUTES)
    return _encode({"sub": str(user_id), "type": "refresh"}, expires)


def decode_token(token: str, kind: str) -> dict:
    """Check the signature and expiry, and that this is the kind of token ("access" or "refresh") expected."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != kind:
        raise jwt.InvalidTokenError(f"Expected a {kind} token")
    return payload
