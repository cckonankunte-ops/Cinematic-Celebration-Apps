"""Authentication endpoints: login, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import InvalidCredentialsError
from app.core.ratelimit import limiter
from app.core.security import (
    ACCESS_COOKIE_NAME,
    CurrentUser,
    create_access_token,
    get_current_user,
    verify_password,
)
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.user import CurrentUserRead, LoginRequest

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    # SameSite=None requires Secure=True; the config defaults are safe for
    # same-domain production, and can be set to none/true for cross-subdomain
    # dev (e.g. GitHub Codespaces).
    samesite = settings.COOKIE_SAMESITE.lower()
    secure = settings.COOKIE_SECURE or samesite == "none"
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,  # type: ignore[arg-type]
        path="/",
        max_age=settings.JWT_EXPIRY_HOURS * 3600,
    )


@router.post("/login", response_model=CurrentUserRead)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    body: LoginRequest = Body(...),
    db: Session = Depends(get_db),
) -> CurrentUserRead:
    """Validate credentials and set an httpOnly auth cookie."""
    row = db.execute(
        select(User, UserRole.name)
        .join(UserRole, User.role_id == UserRole.id)
        .where(User.username == body.username)
    ).first()

    if row is None:
        raise InvalidCredentialsError()
    user, role_name = row
    if not user.is_active or not verify_password(body.password, user.password_hash):
        raise InvalidCredentialsError()

    token = create_access_token(user.id, user.username, role_name, user.location_id)
    _set_auth_cookie(response, token)
    return CurrentUserRead(
        id=user.id, username=user.username, role=role_name, location_id=user.location_id
    )


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """Clear the auth cookie."""
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=CurrentUserRead)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUserRead:
    """Return the current authenticated user."""
    return CurrentUserRead(
        id=user.id, username=user.username, role=user.role, location_id=user.location_id
    )
