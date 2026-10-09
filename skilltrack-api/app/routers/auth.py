from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import ActivityLog, User
from ..ratelimit import login_failures
from ..rules import ensure_common_enrollment
from ..schemas import AccessTokenOut, LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from ..security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


def _token_for(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id),
        user=UserOut.model_validate(user),
    )


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
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
    db.add(ActivityLog(user_id=user.id, action=f"Student {user.name} registered"))
    db.commit()
    return _token_for(user)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    email_key = body.email.lower()
    login_failures.raise_if_blocked(email_key)
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        login_failures.hit(email_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _token_for(user)


@router.post("/auth/refresh", response_model=AccessTokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    """Swap a refresh token for a new access token. The refresh token is not renewed,
    so the user signs in again once it expires."""
    expired = HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Please sign in again.")
    try:
        payload = decode_token(body.refresh_token, "refresh")
        user = db.get(User, int(payload["sub"]))
    except (InvalidTokenError, KeyError, ValueError):
        raise expired
    if user is None or not user.is_active:
        raise expired
    # The role is read from the database, so a role change applies from the next access token
    ends_at = datetime.fromtimestamp(payload["exp"], timezone.utc)
    return AccessTokenOut(access_token=create_access_token(user.id, user.role, not_after=ends_at))


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
