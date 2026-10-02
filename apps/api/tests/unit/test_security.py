"""Unit tests for argon2 hashing and JWT encode/decode."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    CurrentUser,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_round_trip() -> None:
    h = hash_password("s3cret-pass")
    assert h != "s3cret-pass"  # never store plaintext
    assert verify_password("s3cret-pass", h) is True


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("correct-horse")
    assert verify_password("wrong-horse", h) is False


def test_verify_rejects_garbage_hash() -> None:
    assert verify_password("whatever", "not-a-real-hash") is False


def test_token_round_trip() -> None:
    token = create_access_token(42, "staff1", "staff", 2)
    user = decode_access_token(token)
    assert user == CurrentUser(id=42, username="staff1", role="staff", location_id=2)


def test_admin_token_has_null_location() -> None:
    token = create_access_token(1, "admin", "admin", None)
    user = decode_access_token(token)
    assert user is not None
    assert user.role == "admin"
    assert user.location_id is None


def test_decode_rejects_tampered_token() -> None:
    token = create_access_token(1, "admin", "admin", None)
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    assert decode_access_token(tampered) is None


def test_decode_rejects_expired_token() -> None:
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": "1",
            "username": "admin",
            "role": "admin",
            "location_id": None,
            "iat": int((now - timedelta(hours=10)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(expired) is None


def test_decode_rejects_wrong_secret() -> None:
    token = jwt.encode(
        {"sub": "1", "username": "x", "role": "admin", "location_id": None},
        "a-different-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(token) is None


@pytest.mark.parametrize("role", ["admin", "staff"])
def test_role_is_preserved(role: str) -> None:
    user = decode_access_token(create_access_token(5, "u", role, 1))
    assert user is not None
    assert user.role == role
