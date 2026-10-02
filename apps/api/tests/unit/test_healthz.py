"""Smoke test: the app boots and the health endpoint responds."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_returns_ok() -> None:
    app = create_app()
    with TestClient(app) as c:
        resp = c.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
