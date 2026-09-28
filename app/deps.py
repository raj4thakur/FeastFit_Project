from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import AuthenticationError, PermissionDeniedError
from app.models import User
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _user_from_token(token: str, db: Session) -> User:
    user = db.get(User, decode_access_token(token))
    if user is None:
        raise AuthenticationError("User no longer exists")
    if not user.is_active:
        raise PermissionDeniedError("This account is disabled")
    return user


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise AuthenticationError("Not authenticated")
    return _user_from_token(token, db)


def get_optional_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User | None:
    """For public endpoints that personalise output when a valid token is present."""
    if not token:
        return None
    try:
        return _user_from_token(token, db)
    except (AuthenticationError, PermissionDeniedError):
        return None
