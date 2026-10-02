"""Integration tests for admin catalog soft-delete semantics.

Admin "delete" is a deactivate: it sets is_active=False (and effective_to=today)
and the row is NEVER hard-deleted. Deactivated catalog items disappear from the
public listings but remain in the database for historical references.

These tests drive the real HTTP endpoints (with auth + Origin), so they also
cover the router -> service -> model wiring end to end.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cake import Cake
from app.models.plan import Plan
from app.services import catalog
from tests.factories import future_date, make_cake, make_location, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login_admin(client: TestClient, db: Session) -> None:
    """Create an admin and log in so the TestClient holds the auth cookie."""
    make_user(db, "admin", password="pw-123456", location_id=None)
    db.commit()
    # The username is random; fetch the one admin we just created.
    from app.models.user import User
    from app.models.user_role import UserRole

    username = db.execute(
        select(User.username).join(UserRole, User.role_id == UserRole.id).where(
            UserRole.name == "admin"
        )
    ).scalar_one()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def test_deactivate_cake_hides_from_public_but_keeps_row(
    client: TestClient, db: Session
) -> None:
    """DELETE deactivates a cake: gone from public listing, still in the DB."""
    _login_admin(client, db)
    loc = make_location(db)
    cake = make_cake(db, loc.id)
    db.commit()
    on = future_date()

    # Visible in the public listing before deactivation.
    before = catalog.list_cakes(db, loc.id, on)
    assert any(c.id == cake.id for c in before)

    resp = client.delete(f"/api/v1/admin/cakes/{cake.id}", headers=_ORIGIN)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Gone from the public listing...
    after = catalog.list_cakes(db, loc.id, on)
    assert all(c.id != cake.id for c in after)

    # ...but the row still exists (no hard-delete).
    row = db.get(Cake, cake.id)
    assert row is not None
    assert row.is_active is False


def test_delete_is_never_a_hard_delete(client: TestClient, db: Session) -> None:
    """After DELETE, a direct DB query still finds the catalog row."""
    _login_admin(client, db)
    loc = make_location(db)
    cake = make_cake(db, loc.id)
    db.commit()

    client.delete(f"/api/v1/admin/cakes/{cake.id}", headers=_ORIGIN)

    found = db.execute(select(Cake).where(Cake.id == cake.id)).scalar_one_or_none()
    assert found is not None


def test_create_then_update_plan_reflects_changes(
    client: TestClient, db: Session
) -> None:
    """Creating then updating a plan persists the new values."""
    _login_admin(client, db)
    loc = make_location(db)
    db.commit()

    create = client.post(
        "/api/v1/admin/plans",
        headers=_ORIGIN,
        json={
            "location_id": loc.id,
            "title": "Starlight",
            "plan_type": 1,
            "price_paise": 400000,
            "max_people_allowed": 10,
            "effective_from": "2020-01-01",
        },
    )
    assert create.status_code == 201
    plan_id = create.json()["id"]
    assert create.json()["price_paise"] == 400000

    update = client.patch(
        f"/api/v1/admin/plans/{plan_id}",
        headers=_ORIGIN,
        json={"title": "Starlight Deluxe", "price_paise": 450000},
    )
    assert update.status_code == 200
    body = update.json()
    assert body["title"] == "Starlight Deluxe"
    assert body["price_paise"] == 450000

    row = db.get(Plan, plan_id)
    assert row is not None
    assert row.title == "Starlight Deluxe"
    assert row.price_paise == 450000
