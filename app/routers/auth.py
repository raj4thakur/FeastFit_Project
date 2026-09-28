from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.exceptions import AuthenticationError, ConflictError, PermissionDeniedError
from app.models import User
from app.schemas import Token, UserCreate, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Auth"])
settings = get_settings()


@router.post("/register", response_model=UserOut, status_code=201, summary="Create an account")
def register(data: UserCreate, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise ConflictError("An account with this email already exists")
    if db.scalar(select(User.id).where(func.lower(User.username) == data.username.lower())):
        raise ConflictError("This username is already taken")

    is_admin = bool(settings.admin_email) and email == settings.admin_email.lower()
    user = User(
        email=email,
        username=data.username,
        hashed_password=hash_password(data.password),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    return user


@router.post("/login", response_model=Token, summary="Log in with username OR email + password")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    identifier = form.username.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(func.lower(User.email) == identifier, func.lower(User.username) == identifier)
        )
    )
    if user is None or not verify_password(form.password, user.hashed_password):
        raise AuthenticationError("Incorrect username or password")
    if not user.is_active:
        raise PermissionDeniedError("This account is disabled")
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut, summary="Current user profile")
def me(user: User = Depends(get_current_user)):
    return user
