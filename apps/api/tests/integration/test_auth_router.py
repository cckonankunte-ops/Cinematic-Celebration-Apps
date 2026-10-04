"""Auth router + Origin check + login rate-limit tests."""

from __future__ import annotations

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import OriginNotAllowedError
from app.core.security import check_origin
from tests.factories import make_location, make_user

pytestmark = pytest.mark.integration


def _request(method: str, origin: str | None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    return Request({"type": "http", "method": method, "headers": headers})


def test_origin_check_allows_get_without_origin() -> None:
    check_origin(_request("GET", None))  # no raise


def test_origin_check_rejects_disallowed_write_origin() -> None:
    with pytest.raises(OriginNotAllowedError):
        check_origin(_request("POST", "https://evil.example.com"))


def test_origin_check_allows_write_from_allowlisted_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pin the allowlist for this test so it does not depend on the ambient
    # CORS_ALLOWED_ORIGINS env var (which varies by environment, e.g. a
    # Codespace may override it and drop localhost:5173).
    from app.core import security as security_module

    monkeypatch.setattr(
        security_module.settings,
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:4321",
    )
    check_origin(_request("POST", "http://localhost:5173"))  # no raise


def test_login_success_sets_cookie(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    user = make_user(db, "staff", password="pw-123456", location_id=loc.id)
    db.commit()

    resp = client.post(
        "/api/v1/auth/login", json={"username": user.username, "password": "pw-123456"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.cookies
    body = resp.json()
    assert body["role"] == "staff"


def test_login_wrong_password_401(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    user = make_user(db, "staff", password="pw-123456", location_id=loc.id)
    db.commit()

    resp = client.post(
        "/api/v1/auth/login", json={"username": user.username, "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
