from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import REFRESH_COOKIE_NAME
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import User
from ..ratelimit import login_failures
from ..rules import ensure_common_enrollment
from ..schemas import LoginIn, RegisterIn, TokenOut, UserOut
from ..security import hash_password, verify_password
from ..sessions import (
    clear_refresh_cookie, log, revoke, revoke_all, rotate, session_for_token, set_refresh_cookie, start_session,
)

router = APIRouter(tags=["auth"])


def _signed_in(response: Response, user: User, access_token: str, refresh_token: str) -> TokenOut:
    """The refresh token goes only into the httpOnly cookie; the body carries the access token and the user."""
    set_refresh_cookie(response, refresh_token)
    return TokenOut(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Self-registration is always a student; other roles are created by an admin."""
    exists = db.scalar(select(User).where(or_(User.email == body.email, User.reg_no == body.reg_no)))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or register number already registered")
    user = User(
        name=body.name, email=body.email, reg_no=body.reg_no, role="student",
        password_hash=hash_password(body.password), department=body.department,
        semester=1,  # everyone starts in Semester 1; the client cannot choose
    )
    db.add(user)
    db.flush()
    ensure_common_enrollment(db, user)
    log(db, user.id, f"Student {user.name} registered")
    access, refresh_token = start_session(db, user, request)
    db.commit()
    return _signed_in(response, user, access, refresh_token)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email_key = body.email.lower()
    login_failures.raise_if_blocked(email_key)
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        login_failures.hit(email_key)
        log(db, user.id if user else None, f"Failed sign-in for {body.email}")
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    access, refresh_token = start_session(db, user, request)
    log(db, user.id, f"{user.name} signed in")
    db.commit()
    return _signed_in(response, user, access, refresh_token)


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Swap the refresh cookie for a new access token and a new refresh cookie (each refresh token works once).
    Also used on page load to restore the session, since the access token is kept only in page memory."""
    try:
        user, access, refresh_token = rotate(db, request.cookies.get(REFRESH_COOKIE_NAME))
    except HTTPException as exc:
        if exc.status_code != status.HTTP_401_UNAUTHORIZED:
            raise
        ended = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        clear_refresh_cookie(ended)
        return ended
    return _signed_in(response, user, access, refresh_token)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db)):
    """End this browser's session. Works with the cookie alone, even after the access token has expired."""
    session = session_for_token(db, request.cookies.get(REFRESH_COOKIE_NAME))
    if session is not None and session.revoked_at is None:
        revoke(session, "signed out")
        user = db.get(User, session.user_id)
        log(db, session.user_id, f"{user.name if user else 'A user'} signed out")
        db.commit()
    done = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(done)
    return done


@router.post("/auth/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """End every session of the signed-in user, on every device (e.g. after a suspected theft)."""
    ended = revoke_all(db, user.id, "signed out everywhere")
    log(db, user.id, f"{user.name} signed out of all devices ({ended} session{'s' if ended != 1 else ''})")
    db.commit()
    done = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(done)
    return done


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(
    role: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    query = select(User).order_by(User.id)
    if role:
        query = query.where(User.role == role)
    return db.scalars(query).all()
