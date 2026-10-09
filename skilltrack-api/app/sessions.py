"""Sign-in sessions: refresh-token rotation with reuse detection, revocation, and the httpOnly refresh cookie.

Each sign-in is a row in auth_sessions. Access tokens carry its id (`sid`) and are refused once the session ends.
The refresh token is random, lives only in an httpOnly cookie, is stored as a hash, and works once: every refresh
issues a new one. A replaced token showing up again means two parties hold it, so the whole session is ended.
"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import (
    ALGORITHM, ONE_SESSION_PER_STUDENT, SECRET_KEY, REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH, REFRESH_REUSE_GRACE_SECONDS,
    REFRESH_TOKEN_MINUTES, SESSION_IDLE_MINUTES,
)
from .database import SessionLocal
from .models import ActivityLog, AuthSession, RefreshToken, User
from .security import create_access_token, hash_refresh_token, new_refresh_token, new_session_id

SESSION_ENDED = "Your session has ended. Please sign in again."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def log(db: Session, user_id: int | None, action: str) -> None:
    db.add(ActivityLog(user_id=user_id, action=action[:200]))


def is_live(session: AuthSession) -> bool:
    return session.revoked_at is None and _aware(session.expires_at) > _now()


def revoke(session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = _now()
        session.revoke_reason = reason


def revoke_all(db: Session, user_id: int, reason: str) -> int:
    """End every open session of a user. Caller commits."""
    result = db.execute(
        update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=_now(), revoke_reason=reason)
    )
    return result.rowcount or 0


def start_session(db: Session, user: User, request: Request, spent_token: str | None = None) -> tuple[str, str]:
    """Open a session for a user who just signed in. Returns (access token, refresh token). Caller commits.
    `spent_token` is recorded as already used, so presenting it again counts as reuse."""
    if ONE_SESSION_PER_STUDENT and user.role == "student" and revoke_all(db, user.id, "signed in elsewhere"):
        log(db, user.id, f"{user.name} signed in again, so their other session was ended")
    now = _now()
    session = AuthSession(
        id=new_session_id(), user_id=user.id, created_at=now, last_used_at=now,
        expires_at=now + timedelta(minutes=REFRESH_TOKEN_MINUTES),
        user_agent=(request.headers.get("user-agent") or "")[:200] or None,
    )
    db.add(session)
    db.flush()
    if spent_token:
        db.add(RefreshToken(session_id=session.id, token_hash=hash_refresh_token(spent_token), created_at=now, used_at=now))
    token, token_hash = new_refresh_token()
    db.add(RefreshToken(session_id=session.id, token_hash=token_hash, created_at=now))
    return create_access_token(user.id, user.role, session.id, not_after=session.expires_at), token


def rotate(db: Session, raw_token: str | None) -> tuple[User, str, str]:
    """Swap a refresh token for a new access token and a new refresh token. Commits."""
    ended = HTTPException(status.HTTP_401_UNAUTHORIZED, SESSION_ENDED)
    if not raw_token:
        raise ended
    # Locking the row makes two refreshes with the same token take turns, so only one can use it
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)).with_for_update()
    )
    if row is None:
        raise ended
    session = db.get(AuthSession, row.session_id)
    if session is None or not is_live(session):
        raise ended
    user = db.get(User, session.user_id)
    now = _now()
    if user is None or not user.is_active:
        revoke(session, "account inactive")
        db.commit()
        raise ended
    if row.used_at is not None:
        if (now - _aware(row.used_at)).total_seconds() <= REFRESH_REUSE_GRACE_SECONDS:
            # Another tab refreshed with the same cookie a moment ago; its replacement is already in the browser
            raise HTTPException(status.HTTP_409_CONFLICT, "The session was just refreshed. Try again.")
        revoke(session, "refresh token reused")
        log(db, user.id, f"{user.name}: an old sign-in token was used again, so the session was ended (possible theft)")
        db.commit()
        raise ended
    if SESSION_IDLE_MINUTES and now - _aware(session.last_used_at) > timedelta(minutes=SESSION_IDLE_MINUTES):
        revoke(session, "idle")
        db.commit()
        raise ended
    row.used_at = now
    session.last_used_at = now
    token, token_hash = new_refresh_token()
    db.add(RefreshToken(session_id=session.id, token_hash=token_hash, created_at=now))
    access = create_access_token(user.id, user.role, session.id, not_after=_aware(session.expires_at))
    db.commit()
    return user, access, token


def adopt_legacy_token(db: Session, token: str, request: Request) -> tuple[User, str, str]:
    """Transition from the previous version, which kept a signed refresh JWT in localStorage: swap it for a
    session, so nobody is signed out by the upgrade. Tabs still running the old version keep sending the same
    old token every 15 minutes, so a repeat resumes the session it opened instead of counting as theft. That
    session still ends normally (sign-out, deactivation, 1 day), and the old token stops working when it expires.
    Those tokens expire within a day of their sign-in, so a day after deploying this path is unused. Commits."""
    ended = HTTPException(status.HTTP_401_UNAUTHORIZED, SESSION_ENDED)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # checks the signature and expiry
        if payload.get("type") != "refresh" or "sid" in payload:
            raise jwt.InvalidTokenError("Not a refresh token from the previous version")
        user = db.get(User, int(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise ended
    if user is None or not user.is_active:
        raise ended

    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token)))
    if row is None:
        try:
            access, new_token = start_session(db, user, request, spent_token=token)
            db.commit()
            return user, access, new_token
        except IntegrityError:  # another tab swapped the same old token at the same moment: resume its session
            db.rollback()
            row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token)))
            if row is None:
                raise ended

    session = db.get(AuthSession, row.session_id)
    if session is None or session.user_id != user.id or not is_live(session):
        raise ended
    now = _now()
    session.last_used_at = now
    new_token, new_hash = new_refresh_token()
    db.add(RefreshToken(session_id=session.id, token_hash=new_hash, created_at=now))
    access = create_access_token(user.id, user.role, session.id, not_after=_aware(session.expires_at))
    db.commit()
    return user, access, new_token


def session_for_token(db: Session, raw_token: str | None) -> AuthSession | None:
    if not raw_token:
        return None
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)))
    return db.get(AuthSession, row.session_id) if row else None


def set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    # Lives exactly as long as its session, so closing the browser does not sign the user out
    max_age = max(0, int((_aware(expires_at) - _now()).total_seconds()))
    response.set_cookie(
        REFRESH_COOKIE_NAME, token, max_age=max_age, httponly=True, secure=True, samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, secure=True, httponly=True, samesite="strict")


def purge_old_sessions() -> None:
    """Scheduled job: delete sessions (and, by cascade, their refresh tokens) that ended over a day ago."""
    cutoff = _now() - timedelta(days=1)
    with SessionLocal() as db:
        db.execute(delete(AuthSession).where(or_(AuthSession.expires_at < cutoff, AuthSession.revoked_at < cutoff)))
        db.commit()
