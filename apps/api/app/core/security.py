"""Password hashing (argon2) and JWT encode/decode.

argon2 is tuned for a small VPS: ~19 MB per hash, 2 iterations, single lane.
Password hashes are never logged or returned. Auth/role dependencies live in
this module too (added in task 4); task 3 provides the primitives.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import (
    ForbiddenError,
    LocationAccessDeniedError,
    OriginNotAllowedError,
    UnauthenticatedError,
)

ACCESS_COOKIE_NAME = "access_token"
_WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

# Tuned for a 1-2 GB VPS.
_hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)


def hash_password(plain: str) -> str:
    """Return an argon2 hash for the given plaintext password."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if the plaintext matches the argon2 hash, else False."""
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated principal extracted from a validated JWT."""

    id: int
    username: str
    role: str
    location_id: int | None


def create_access_token(user_id: int, username: str, role: str, location_id: int | None) -> str:
    """Create a signed JWT for the given user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "location_id": location_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.JWT_EXPIRY_HOURS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> CurrentUser | None:
    """Decode and validate a JWT. Returns CurrentUser or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None
    try:
        return CurrentUser(
            id=int(payload["sub"]),
            username=payload["username"],
            role=payload["role"],
            location_id=payload.get("location_id"),
        )
    except (KeyError, ValueError, TypeError):
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    """Resolve the authenticated user from the access_token cookie.

    Raises UnauthenticatedError if the token is missing/invalid/expired or the
    user no longer exists or is inactive.
    """
    from app.models.user import User  # local import to avoid circular import

    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        raise UnauthenticatedError()
    claims = decode_access_token(token)
    if claims is None:
        raise UnauthenticatedError()

    user = db.execute(select(User).where(User.id == claims.id)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthenticatedError()

    return CurrentUser(
        id=user.id,
        username=user.username,
        role=claims.role,
        location_id=user.location_id,
    )


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """FastAPI dependency factory enforcing that the current user has a role.

    Usage: Depends(require_role("admin")) or Depends(require_role("admin", "staff")).
    """

    def _dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if roles and user.role not in roles:
            raise ForbiddenError()
        return user

    return _dependency


def check_origin(request: Request) -> None:
    """Reject state-changing requests whose Origin is not in the allowlist.

    CSRF defense layered on top of SameSite=Lax cookies.
    """
    if request.method in _WRITE_METHODS:
        origin = request.headers.get("origin")
        if origin is None or origin not in settings.cors_origins:
            raise OriginNotAllowedError()


def assert_location_access(actor: CurrentUser, location_id: int) -> None:
    """Allow admins everywhere; restrict staff to their assigned location."""
    if actor.role == "admin":
        return
    if actor.location_id != location_id:
        raise LocationAccessDeniedError()
