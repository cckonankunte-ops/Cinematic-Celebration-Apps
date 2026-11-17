"""'admin_only' special-decor category: hidden from and rejected for customers,
available to staff/admin in the booking form and previews (real PG)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    future_date,
    make_decor,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login(client: TestClient, username: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def _body(loc_id: int, plan_id: int, slot_id: int, decor_id: int) -> dict:
    return {
        "location_id": loc_id,
        "plan_id": plan_id,
        "slot_id": slot_id,
        "booking_date": future_date().isoformat(),
        "people": 2,
        "special_decor": [{"id": decor_id, "quantity": 1}],
        "combos": [],
    }


def test_public_decor_list_excludes_admin_only(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    normal = make_decor(db, loc.id)
    hidden = make_decor(db, loc.id, sort_order=2)
    hidden.category = "admin_only"
    db.commit()

    resp = client.get(f"/api/v1/public/locations/{loc.id}/special-decor")
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert normal.id in ids
    assert hidden.id not in ids


def test_public_preview_rejects_admin_only_decor(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    hidden = make_decor(db, loc.id)
    hidden.category = "admin_only"
    db.commit()

    resp = client.post(
        "/api/v1/public/bookings/preview",
        json=_body(loc.id, plan.id, slot.id, hidden.id),
        headers=_ORIGIN,
    )
    assert resp.status_code == 422


def test_admin_preview_and_booking_options_include_admin_only(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    hidden = make_decor(db, loc.id)
    hidden.category = "admin_only"
    admin = make_user(db, "admin", password="pw-123456", location_id=None)
    db.commit()
    _login(client, admin.username)

    opts = client.get(
        f"/api/v1/admin/booking-options/special-decor?location_id={loc.id}"
    )
    assert opts.status_code == 200
    assert hidden.id in [d["id"] for d in opts.json()]

    resp = client.post(
        "/api/v1/admin/bookings/preview",
        json=_body(loc.id, plan.id, slot.id, hidden.id),
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def test_staff_cannot_list_other_location_booking_options(
    client: TestClient, db: Session
) -> None:
    loc1 = make_location(db)
    loc2 = make_location(db)
    staff = make_user(db, "staff", password="pw-123456", location_id=loc1.id)
    db.commit()
    _login(client, staff.username)

    assert (
        client.get(
            f"/api/v1/admin/booking-options/special-decor?location_id={loc1.id}"
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/admin/booking-options/special-decor?location_id={loc2.id}"
        ).status_code
        == 403
    )
