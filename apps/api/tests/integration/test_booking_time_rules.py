"""Booking-time rules at create/edit (overlap, buffer, hours, cutoff, future).

Exercises the service-layer rule pipeline + overlap pre-check through the HTTP
layer. The DB exclusion constraint is the concurrency backstop (migration B);
these tests assert the user-facing behaviour and error codes.
"""

from __future__ import annotations

from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import future_date, make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _public_book(client: TestClient, loc, plan, slot, when: str):
    return client.post(
        "/api/v1/public/bookings",
        headers=_ORIGIN,
        json={
            "location_id": loc,
            "plan_id": plan,
            "slot_id": slot,
            "booking_date": when,
            "booking_name": "Priya S",
            "phone": "9876543210",
            "people": 4,
            "special_decor": [],
            "combos": [],
        },
    )


def test_overlapping_one_and_two_hour_one_wins(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    two_hour = make_slot(
        db, plan.id, start_time=time(15, 0), duration_minutes=120, sort_order=1
    )
    one_hour = make_slot(
        db, plan.id, start_time=time(15, 30), duration_minutes=60, sort_order=2
    )  # overlaps 15:00-17:00
    db.commit()
    when = future_date().isoformat()

    r1 = _public_book(client, loc.id, plan.id, two_hour.id, when)
    assert r1.status_code == 201
    r2 = _public_book(client, loc.id, plan.id, one_hour.id, when)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "SLOT_UNAVAILABLE"


def test_back_to_back_after_buffer_both_succeed(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    first = make_slot(
        db, plan.id, start_time=time(15, 0), duration_minutes=60, sort_order=1
    )  # occupies 15:00-16:30 with 30-min buffer
    after = make_slot(
        db, plan.id, start_time=time(16, 30), duration_minutes=60, sort_order=2
    )
    db.commit()
    when = future_date().isoformat()

    assert _public_book(client, loc.id, plan.id, first.id, when).status_code == 201
    assert _public_book(client, loc.id, plan.id, after.id, when).status_code == 201


def test_public_end_after_close_rejected(client: TestClient, db: Session) -> None:
    loc = make_location(db)  # closes 01:00
    plan = make_plan(db, loc.id)
    loc.allow_late_booking = True  # allow the late start so we hit end-before-close
    late = make_slot(
        db, plan.id, start_time=time(0, 0), duration_minutes=120, sort_order=1
    )  # 00:00 + 2h = 02:00 > close 01:00
    db.commit()

    resp = _public_book(client, loc.id, plan.id, late.id, future_date().isoformat())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "BOOKING_ENDS_AFTER_CLOSE"


def test_admin_overrides_end_after_close(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    admin = make_user(db, "admin", location_id=None)
    late = make_slot(
        db, plan.id, start_time=time(0, 0), duration_minutes=120, sort_order=1
    )
    db.commit()
    client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    resp = client.post(
        "/api/v1/admin/bookings",
        headers=_ORIGIN,
        json={
            "location_id": loc.id,
            "plan_id": plan.id,
            "slot_id": late.id,
            "booking_date": future_date().isoformat(),
            "booking_name": "Late Admin",
            "phone": "9876543210",
            "people": 4,
            "special_decor": [],
            "combos": [],
        },
    )
    assert resp.status_code == 201  # admin may end after close
