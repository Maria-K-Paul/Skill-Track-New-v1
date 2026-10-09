from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, User
from .security import decode_access_token
from .sessions import is_live

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if creds is None:
        raise unauthorized
    try:
        payload = decode_access_token(creds.credentials)
        user_id, session_id = int(payload["sub"]), str(payload["sid"])
    except (InvalidTokenError, KeyError, ValueError):
        raise unauthorized
    # The token's session must still be open: signing out, a detected token theft or a deactivation ends it,
    # and its access tokens stop working immediately instead of at expiry
    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != user_id or not is_live(session):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return checker
