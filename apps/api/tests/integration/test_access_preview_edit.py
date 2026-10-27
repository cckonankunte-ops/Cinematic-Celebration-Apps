"""Preview/edit role + location access control (real admin HTTP endpoints).

Feature: admin-booking-edit, Property 18: Role and location access control.

Drives POST /api/v1/admin/bookings/preview and PATCH
/api/v1/admin/bookings/{id}:
- Unauthenticated requests are rejected (401).
- Staff may only preview/edit bookings for their assigned location (403 cross).
- Admins may preview/edit any location.

Validates: Requirements 2.6, 6.6, 9.1, 9.3, 9.4, 9.5
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    future_date,
    make_booking,
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


def _preview_body(location_id: int, plan_id: int, slot_id: int) -> dict:
    return {
        "location_id": location_id,
        "plan_id": plan_id,
        "slot_id": slot_id,
        "booking_date": future_date().isoformat(),
        "people": 4,
        "special_decor": [],
        "combos": [],
    }


def test_unauthenticated_preview_rejected(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    db.commit()

    resp = client.post(
        "/api/v1/admin/bookings/preview",
        headers=_ORIGIN,
        json=_preview_body(loc.id, plan.id, slot.id),
    )
    assert resp.status_code == 401


def test_staff_cross_location_preview_and_edit_denied(
    client: TestClient, db: Session
) -> None:
    loc1 = make_location(db, name="Hulimavu")
    loc2 = make_location(db, name="Konankunte")
    staff = make_user(db, "staff", location_id=loc1.id)
    plan2 = make_plan(db, loc2.id)
    slot2 = make_slot(db, plan2.id)
    loc2_booking = make_booking(
        db, location_id=loc2.id, plan_id=plan2.id, slot_id=slot2.id, status="accepted"
    )
    db.commit()

    _login(client, staff.username)

    preview = client.post(
        "/api/v1/admin/bookings/preview",
        headers=_ORIGIN,
        json=_preview_body(loc2.id, plan2.id, slot2.id),
    )
    assert preview.status_code == 403
    assert preview.json()["error"]["code"] == "LOCATION_ACCESS_DENIED"

    edit = client.patch(
        f"/api/v1/admin/bookings/{loc2_booking.id}",
        headers=_ORIGIN,
        json={"people": 5},
    )
    assert edit.status_code == 403
    assert edit.json()["error"]["code"] == "LOCATION_ACCESS_DENIED"


def test_staff_own_location_preview_and_edit_allowed(
    client: TestClient, db: Session
) -> None:
    loc1 = make_location(db, name="Hulimavu")
    staff = make_user(db, "staff", location_id=loc1.id)
    plan1 = make_plan(db, loc1.id, max_people_allowed=10)
    slot1 = make_slot(db, plan1.id)
    loc1_booking = make_booking(
        db, location_id=loc1.id, plan_id=plan1.id, slot_id=slot1.id, status="accepted"
    )
    db.commit()

    _login(client, staff.username)

    preview = client.post(
        "/api/v1/admin/bookings/preview",
        headers=_ORIGIN,
        json=_preview_body(loc1.id, plan1.id, slot1.id),
    )
    assert preview.status_code == 200

    edit = client.patch(
        f"/api/v1/admin/bookings/{loc1_booking.id}",
        headers=_ORIGIN,
        json={"people": 5},
    )
    assert edit.status_code == 200
    assert edit.json()["people"] == 5


def test_admin_any_location_preview_and_edit_allowed(
    client: TestClient, db: Session
) -> None:
    loc2 = make_location(db, name="Konankunte")
    admin = make_user(db, "admin", location_id=None)
    plan2 = make_plan(db, loc2.id, max_people_allowed=10)
    slot2 = make_slot(db, plan2.id)
    loc2_booking = make_booking(
        db, location_id=loc2.id, plan_id=plan2.id, slot_id=slot2.id, status="accepted"
    )
    db.commit()

    _login(client, admin.username)

    preview = client.post(
        "/api/v1/admin/bookings/preview",
        headers=_ORIGIN,
        json=_preview_body(loc2.id, plan2.id, slot2.id),
    )
    assert preview.status_code == 200

    edit = client.patch(
        f"/api/v1/admin/bookings/{loc2_booking.id}",
        headers=_ORIGIN,
        json={"people": 6},
    )
    assert edit.status_code == 200
    assert edit.json()["people"] == 6
