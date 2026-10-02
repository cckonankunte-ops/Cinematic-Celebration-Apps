"""Role / location access-control integration test (mandatory case from tech.md).

Drives the real admin HTTP endpoints:
- Staff assigned to location 1 cannot read/create bookings for location 2 (403).
- Analytics requires the admin role (staff -> 403).
- Admins can access any location.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login(client: TestClient, username: str, password: str = "pw-123456") -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def test_staff_cannot_read_other_location_bookings(client: TestClient, db: Session) -> None:
    loc1 = make_location(db, name="Hulimavu")
    loc2 = make_location(db, name="Konankunte")
    staff = make_user(db, "staff", location_id=loc1.id)
    db.commit()

    _login(client, staff.username)

    ok = client.get(f"/api/v1/admin/bookings?location_id={loc1.id}", headers=_ORIGIN)
    assert ok.status_code == 200

    denied = client.get(f"/api/v1/admin/bookings?location_id={loc2.id}", headers=_ORIGIN)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "LOCATION_ACCESS_DENIED"


def test_staff_cannot_create_booking_for_other_location(
    client: TestClient, db: Session
) -> None:
    loc1 = make_location(db, name="Hulimavu")
    loc2 = make_location(db, name="Konankunte")
    plan2 = make_plan(db, loc2.id)
    slot2 = make_slot(db, plan2.id)
    staff = make_user(db, "staff", location_id=loc1.id)
    db.commit()

    _login(client, staff.username)

    resp = client.post(
        "/api/v1/admin/bookings",
        headers=_ORIGIN,
        json={
            "location_id": loc2.id,
            "plan_id": plan2.id,
            "slot_id": slot2.id,
            "booking_date": "2099-01-01",
            "booking_name": "X",
            "email": "x@example.com",
            "people": 4,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "LOCATION_ACCESS_DENIED"


def test_analytics_requires_admin(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    staff = make_user(db, "staff", location_id=loc.id)
    db.commit()

    _login(client, staff.username)

    resp = client.get(
        f"/api/v1/admin/analytics/slot-amounts?location_id={loc.id}&date=2099-01-01",
        headers=_ORIGIN,
    )
    assert resp.status_code == 403


def test_admin_can_access_any_location(client: TestClient, db: Session) -> None:
    loc1 = make_location(db, name="Hulimavu")
    loc2 = make_location(db, name="Konankunte")
    admin = make_user(db, "admin", location_id=None)
    db.commit()

    _login(client, admin.username)

    for loc in (loc1, loc2):
        resp = client.get(f"/api/v1/admin/bookings?location_id={loc.id}", headers=_ORIGIN)
        assert resp.status_code == 200
    analytics = client.get(
        f"/api/v1/admin/analytics/slot-amounts?location_id={loc1.id}&date=2099-01-01",
        headers=_ORIGIN,
    )
    assert analytics.status_code == 200
