"""End-to-end Phase 1 flow: customer request -> staff confirm.

Exercises the full loop through the HTTP layer with the ManualProvider:
1. POST /public/bookings creates a pending booking holding the slot and returns
   a token + payment instructions (no payment URL).
2. GET /public/bookings/{token} shows pending.
3. A second request for the same slot/date gets 409 SLOT_UNAVAILABLE.
4. Staff log in, record an advance >= plan.advance_paise.
5. Staff accept the booking -> accepted; an 'accepted' event is written.
6. GET /public/bookings/{token} shows accepted with correct derived amounts.
7. Exactly one booking_event exists per state change.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.booking_event import BookingEvent
from tests.factories import future_date, make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _booking_payload(location_id: int, plan_id: int, slot_id: int) -> dict:
    return {
        "location_id": location_id,
        "plan_id": plan_id,
        "slot_id": slot_id,
        "booking_date": future_date().isoformat(),
        "booking_name": "Priya S",
        "email": "priya@example.com",
        "phone": "9876543210",
        "people": 4,
        "special_decor_ids": [],
        "combo_ids": [],
    }


def test_full_booking_request_to_confirmation(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id, advance_paise=50000)
    slot = make_slot(db, plan.id)
    staff = make_user(db, "admin", location_id=None)
    db.commit()

    payload = _booking_payload(loc.id, plan.id, slot.id)

    # 1. Customer booking request -> pending + token + instructions, no payment URL.
    created = client.post("/api/v1/public/bookings", json=payload, headers=_ORIGIN)
    assert created.status_code == 201
    body = created.json()
    token = body["booking_token"]
    assert body["advance_paise"] == 50000
    assert "payment_instructions" in body
    assert "payment_url" not in body

    # 2. Public status lookup shows pending.
    status = client.get(f"/api/v1/public/bookings/{token}")
    assert status.status_code == 200
    assert status.json()["status"] == "pending"

    # 3. Second request for the same slot/date -> 409.
    conflict = client.post("/api/v1/public/bookings", json=payload, headers=_ORIGIN)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "SLOT_UNAVAILABLE"

    # Resolve the booking id from the token for admin calls.
    booking = db.execute(
        select(Booking).where(Booking.public_token == token)
    ).scalar_one()

    # 4. Staff log in and record an advance >= plan.advance_paise.
    login = client.post(
        "/api/v1/auth/login",
        json={"username": staff.username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert login.status_code == 200

    pay = client.post(
        f"/api/v1/admin/bookings/{booking.id}/payments",
        json={"method": "upi", "amount_paise": 50000, "note": "advance"},
        headers=_ORIGIN,
    )
    assert pay.status_code == 201

    # 5. Accept the booking.
    accept = client.post(
        f"/api/v1/admin/bookings/{booking.id}/accept",
        json={"override_advance": False},
        headers=_ORIGIN,
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    # 6. Public status now shows accepted with correct derived amounts.
    final = client.get(f"/api/v1/public/bookings/{token}").json()
    assert final["status"] == "accepted"
    assert final["amount_paid_paise"] == 50000
    assert final["amount_due_paise"] == final["total_paise"] - 50000

    # 7. One event per state change: created, payment_recorded, accepted.
    event_types = db.execute(
        select(BookingEvent.event_type).where(BookingEvent.booking_id == booking.id)
    ).scalars().all()
    assert sorted(event_types) == ["accepted", "created", "payment_recorded"]
    # Exactly one accepted event.
    accepted_count = db.execute(
        select(func.count())
        .select_from(BookingEvent)
        .where(
            BookingEvent.booking_id == booking.id,
            BookingEvent.event_type == "accepted",
        )
    ).scalar_one()
    assert accepted_count == 1


def test_accept_blocked_without_advance(client: TestClient, db: Session) -> None:
    """Accepting with no recorded advance is rejected (422)."""
    loc = make_location(db)
    plan = make_plan(db, loc.id, advance_paise=50000)
    slot = make_slot(db, plan.id)
    staff = make_user(db, "admin", location_id=None)
    db.commit()

    created = client.post(
        "/api/v1/public/bookings",
        json=_booking_payload(loc.id, plan.id, slot.id),
        headers=_ORIGIN,
    )
    token = created.json()["booking_token"]
    booking = db.execute(
        select(Booking).where(Booking.public_token == token)
    ).scalar_one()

    client.post(
        "/api/v1/auth/login",
        json={"username": staff.username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    resp = client.post(
        f"/api/v1/admin/bookings/{booking.id}/accept",
        json={"override_advance": False},
        headers=_ORIGIN,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ACCEPT_REQUIRES_ADVANCE"
