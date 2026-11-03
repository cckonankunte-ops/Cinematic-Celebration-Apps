"""Admin add-on management: image-upload URL + reactivate via PATCH.

Covers the Catalog add-on management surface added for cakes/decor/combos:
- POST /admin/catalog-image-uploads returns an object key + presigned URL and
  creates no row;
- deactivate (soft-delete) then PATCH is_active=true + effective_to reactivates
  an item (the UI's "Activate" path).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_cake, make_location, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login_admin(client: TestClient, db: Session) -> None:
    admin = make_user(db, "admin", location_id=None)
    db.commit()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def test_catalog_image_upload_returns_key_and_url(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stub the R2 presign so the test doesn't need live storage credentials.
    monkeypatch.setattr(
        "app.services.catalog_admin.create_upload_url",
        lambda object_key, expires_in=900: f"https://r2.example/put/{object_key}",
    )
    _login_admin(client, db)
    resp = client.post(
        "/api/v1/admin/catalog-image-uploads",
        headers=_ORIGIN,
        json={"kind": "cake", "filename": "truffle.jpg"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["object_key"].startswith("cakes/")
    assert body["object_key"].endswith("truffle.jpg")
    assert body["upload_url"].startswith("https://r2.example/put/cakes/")


def test_catalog_image_upload_rejects_unknown_kind(
    client: TestClient, db: Session
) -> None:
    _login_admin(client, db)
    resp = client.post(
        "/api/v1/admin/catalog-image-uploads",
        headers=_ORIGIN,
        json={"kind": "banana", "filename": "x.jpg"},
    )
    # Literal validation rejects an unknown kind at the schema layer.
    assert resp.status_code == 422


def test_deactivate_then_reactivate_cake(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    cake = make_cake(db, loc.id)
    db.commit()
    _login_admin(client, db)

    # Deactivate (soft-delete): is_active False, effective_to pulled to today.
    resp = client.delete(f"/api/v1/admin/cakes/{cake.id}", headers=_ORIGIN)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Reactivate via PATCH (the UI "Activate" path): is_active + far-future end.
    resp = client.patch(
        f"/api/v1/admin/cakes/{cake.id}",
        headers=_ORIGIN,
        json={"is_active": True, "effective_to": "2099-12-31"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is True
    assert body["effective_to"].startswith("2099-12-31")

    # It now appears active in the admin list.
    resp = client.get(
        f"/api/v1/admin/cakes?location_id={loc.id}", headers=_ORIGIN
    )
    assert resp.status_code == 200
    active = [c for c in resp.json() if c["id"] == cake.id and c["is_active"]]
    assert len(active) == 1
