"""Admin plan-gallery management: list + delete (real Postgres).

The admin gallery panel needs to list a plan's saved images (with ids) so it can
display thumbnails and delete them. This covers:
- GET /admin/plans/{id}/gallery returns registered images with ids + urls,
- DELETE removes one and the list reflects it.
The presigned-PUT (R2) step is not exercised; we register rows via the service.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import catalog_admin
from tests.factories import make_location, make_plan, make_user

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


def test_list_and_delete_plan_gallery(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    # Register two gallery rows directly via the service (no R2 needed).
    img1 = catalog_admin.add_gallery_image(db, plan.id, "plans/x/a.jpg", 0)
    img2 = catalog_admin.add_gallery_image(db, plan.id, "plans/x/b.jpg", 1)
    db.commit()
    _login_admin(client, db)

    # List returns both, with ids and image_urls.
    resp = client.get(f"/api/v1/admin/plans/{plan.id}/gallery", headers=_ORIGIN)
    assert resp.status_code == 200
    rows = resp.json()
    assert {r["id"] for r in rows} == {img1.id, img2.id}
    assert all(r["image_url"] for r in rows)

    # Delete one; the list now has only the other.
    resp = client.delete(
        f"/api/v1/admin/plans/{plan.id}/gallery/{img1.id}", headers=_ORIGIN
    )
    assert resp.status_code == 204

    resp = client.get(f"/api/v1/admin/plans/{plan.id}/gallery", headers=_ORIGIN)
    assert [r["id"] for r in resp.json()] == [img2.id]
