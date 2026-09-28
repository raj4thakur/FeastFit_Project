"""Password hashing (PBKDF2-HMAC-SHA256, stdlib only) and JWT access tokens."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from app.exceptions import AuthenticationError

settings = get_settings()
_SCHEME = "pbkdf2_sha256"


def _pbkdf2(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or settings.password_iterations
    salt = os.urandom(16)
    digest = _pbkdf2(password, salt, iterations)
    return "$".join(
        [_SCHEME, str(iterations), base64.b64encode(salt).decode(), base64.b64encode(digest).decode()]
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = stored_hash.split("$")
        if scheme != _SCHEME:
            return False
        expected = base64.b64decode(digest_b64)
        actual = _pbkdf2(password, base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, expires_minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    minutes = settings.access_token_expire_minutes if expires_minutes is None else expires_minutes
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired token") from exc
