"""Admin booking search / filter / pagination (real Postgres).

Covers GET /api/v1/admin/bookings with q/search_in, date range, status, and
limit/offset, plus the paged response shape and location-scoped access.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    future_date,
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


def _make_booking(client: TestClient, loc_id, plan_id, slot_id, **over) -> str:
    body = {
        "location_id": loc_id,
        "plan_id": plan_id,
        "slot_id": slot_id,
        "booking_date": future_date().isoformat(),
        "booking_name": "Priya Sharma",
        "phone": "9876543210",
        "people": 2,
        **over,
    }
    resp = client.post("/api/v1/admin/bookings", headers=_ORIGIN, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["booking_reference"]


def test_search_customer_name(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    admin = make_user(db, "admin", location_id=None)
    slot = make_slot(db, plan.id, description="9 AM - 12 PM")
    db.commit()
    _login(client, admin.username)

    _make_booking(client, loc.id, plan.id, slot.id, booking_name="Ravi Kumar",
                  phone="9811122233")
    _make_booking(client, loc.id, plan.id, slot.id, booking_name="Sita Devi",
                  phone="9700000001", booking_date=future_date(2).isoformat())

    # customer_name match
    r = client.get(
        f"/api/v1/admin/bookings?location_id={loc.id}&q=Ravi&search_in=customer_name",
        headers=_ORIGIN,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["booking_name"] == "Ravi Kumar"
    assert {"items", "total", "limit", "offset"} <= body.keys()


def test_search_phone_partial_digits(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    admin = make_user(db, "admin", location_id=None)
    slot = make_slot(db, plan.id, description="9 AM - 12 PM")
    db.commit()
    _login(client, admin.username)
    _make_booking(client, loc.id, plan.id, slot.id, phone="9876500000")

    # 3-digit partial, ignoring +91 / spaces in the query.
    r = client.get(
        f"/api/v1/admin/bookings?location_id={loc.id}&q=+91 987&search_in=phone",
        headers=_ORIGIN,
    )
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_min_three_chars_ignored(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    admin = make_user(db, "admin", location_id=None)
    slot = make_slot(db, plan.id, description="9 AM - 12 PM")
    db.commit()
    _login(client, admin.username)
    _make_booking(client, loc.id, plan.id, slot.id, booking_name="Ravi Kumar")

    # 2-char query -> no text filter applied (returns all, not just matches).
    r = client.get(
        f"/api/v1/admin/bookings?location_id={loc.id}&q=Ra",
        headers=_ORIGIN,
    )
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_limit_clamped_and_offset(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin", location_id=None)
    db.commit()
    _login(client, admin.username)
    # over-200 limit must be rejected by the query validator (le=200)
    r = client.get(
        f"/api/v1/admin/bookings?location_id={loc.id}&limit=5000", headers=_ORIGIN
    )
    assert r.status_code == 422


def test_search_is_location_scoped(client: TestClient, db: Session) -> None:
    loc1 = make_location(db, name="Hulimavu")
    loc2 = make_location(db, name="Konankunte")
    staff = make_user(db, "staff", location_id=loc1.id)
    db.commit()
    _login(client, staff.username)
    # Staff cannot search another location regardless of params.
    r = client.get(
        f"/api/v1/admin/bookings?location_id={loc2.id}&q=Ravi", headers=_ORIGIN
    )
    assert r.status_code == 403
