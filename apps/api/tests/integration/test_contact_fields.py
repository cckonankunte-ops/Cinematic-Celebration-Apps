"""Integration test — contact fields on booking create (real PostgreSQL).

Feature: admin-booking-edit, Property 26: Blank or invalid phone is rejected;
email is optional. A public booking create with a missing, blank, or
non-normalizable phone returns 422 and persists nothing; a create with a valid
phone and NO email succeeds (201) and stores a null email.

Validates: Requirements 22.2, 22.3, 23.3
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from tests.factories import future_date, make_location, make_plan, make_slot

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _seed(db: Session) -> tuple[int, int, int]:
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    db.commit()
    return loc.id, plan.id, slot.id


def _payload(loc_id: int, plan_id: int, slot_id: int) -> dict:
    return {
        "location_id": loc_id,
        "plan_id": plan_id,
        "slot_id": slot_id,
        "booking_date": future_date().isoformat(),
        "booking_name": "Priya S",
        "people": 4,
        "special_decor": [],
        "combos": [],
    }


def _booking_count(db: Session) -> int:
    return int(db.execute(select(func.count()).select_from(Booking)).scalar_one())


def test_missing_phone_is_rejected_and_persists_nothing(
    client: TestClient, db: Session
) -> None:
    loc_id, plan_id, slot_id = _seed(db)
    payload = _payload(loc_id, plan_id, slot_id)  # no "phone" key at all

    resp = client.post("/api/v1/public/bookings", json=payload, headers=_ORIGIN)
    assert resp.status_code == 422
    assert _booking_count(db) == 0


def test_blank_phone_is_rejected(client: TestClient, db: Session) -> None:
    loc_id, plan_id, slot_id = _seed(db)
    payload = _payload(loc_id, plan_id, slot_id)
    payload["phone"] = ""

    resp = client.post("/api/v1/public/bookings", json=payload, headers=_ORIGIN)
    assert resp.status_code == 422
    assert _booking_count(db) == 0


def test_non_normalizable_phone_is_rejected(client: TestClient, db: Session) -> None:
    loc_id, plan_id, slot_id = _seed(db)
    payload = _payload(loc_id, plan_id, slot_id)
    payload["phone"] = "12345"

    resp = client.post("/api/v1/public/bookings", json=payload, headers=_ORIGIN)
    assert resp.status_code == 422
    assert _booking_count(db) == 0


def test_valid_phone_without_email_is_accepted_and_email_is_null(
    client: TestClient, db: Session
) -> None:
    loc_id, plan_id, slot_id = _seed(db)
    payload = _payload(loc_id, plan_id, slot_id)
    payload["phone"] = "9876543210"  # valid; NO email key

    resp = client.post("/api/v1/public/bookings", json=payload, headers=_ORIGIN)
    assert resp.status_code == 201

    token = resp.json()["booking_token"]
    booking = db.execute(
        select(Booking).where(Booking.public_token == token)
    ).scalar_one()
    assert booking.email is None
    assert booking.phone == "9876543210"
