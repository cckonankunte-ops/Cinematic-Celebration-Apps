"""Unit tests for the error envelope and exception handlers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import (
    SlotUnavailableError,
    register_exception_handlers,
)


def _app_with_failing_routes() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/slot")
    def _slot() -> None:
        raise SlotUnavailableError()

    @app.get("/boom")
    def _boom() -> None:
        raise RuntimeError("unexpected")

    return app


def test_app_error_renders_envelope() -> None:
    with TestClient(_app_with_failing_routes(), raise_server_exceptions=False) as c:
        resp = c.get("/slot")
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "SLOT_UNAVAILABLE",
            "message": "This slot is already booked for the selected date.",
        }
    }


def test_unexpected_error_renders_generic_500() -> None:
    with TestClient(_app_with_failing_routes(), raise_server_exceptions=False) as c:
        resp = c.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
