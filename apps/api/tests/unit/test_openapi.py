"""The OpenAPI schema (frontend contract) must generate successfully."""

from __future__ import annotations

from app.main import create_app


def test_openapi_schema_generates() -> None:
    app = create_app()
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    paths = schema["paths"]
    # A few representative routes across the surface must be present.
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/public/bookings" in paths
    assert "/api/v1/admin/bookings" in paths
    assert "/healthz" in paths
