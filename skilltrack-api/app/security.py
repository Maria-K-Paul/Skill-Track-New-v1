import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import ACCESS_TOKEN_MINUTES, ALGORITHM, SECRET_KEY


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int, role: str, session_id: str, not_after: datetime | None = None) -> str:
    """Short-lived token sent with every request. `sid` ties it to its sign-in session, which the server checks on
    every request; `not_after` keeps it from outliving the session."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    if not_after is not None:
        expires = min(expires, not_after)
    claims = {"sub": str(user_id), "role": role, "sid": session_id, "type": "access", "iat": now, "exp": expires}
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Check the signature and expiry, and that this is an access token."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "access" or "sid" not in payload:
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def new_session_id() -> str:
    return secrets.token_hex(16)


def new_refresh_token() -> tuple[str, str]:
    """A random refresh token and the SHA-256 hash that is stored instead of it."""
    token = secrets.token_urlsafe(32)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
