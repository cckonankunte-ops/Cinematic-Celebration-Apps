"""Slot availability flagging for the booking UIs.

POST /api/v1/public/plans/{id}/available-slots returns ALL active slots for the
plan/date, each annotated with `is_available`. A slot held by an active
(pending|accepted) booking is flagged unavailable so the booking UIs can grey
it out rather than hide it. The DB partial unique index remains the real guard.
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
)

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _book(client: TestClient, loc_id: int, plan_id: int, slot_id: int, when: str) -> None:
    resp = client.post(
        "/api/v1/public/bookings",
        headers=_ORIGIN,
        json={
            "location_id": loc_id,
            "plan_id": plan_id,
            "slot_id": slot_id,
            "booking_date": when,
            "booking_name": "Priya S",
            "phone": "9876543210",
            "people": 4,
            "special_decor": [],
            "combos": [],
        },
    )
    assert resp.status_code == 201


def test_held_slot_flagged_unavailable(client: TestClient, db: Session) -> None:
    """A slot held by an active booking is returned with is_available=False;
    a free slot on the same plan/date is is_available=True."""
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    booked = make_slot(db, plan.id, description="9 AM - 12 PM", sort_order=1)
    free = make_slot(db, plan.id, description="1 PM - 4 PM", sort_order=2)
    db.commit()

    when = future_date().isoformat()
    _book(client, loc.id, plan.id, booked.id, when)

    resp = client.post(
        f"/api/v1/public/plans/{plan.id}/available-slots",
        headers=_ORIGIN,
        json={"location_id": loc.id, "booking_date": when},
    )
    assert resp.status_code == 200
    by_id = {s["id"]: s for s in resp.json()}

    # Both slots are returned (held slot is NOT hidden).
    assert set(by_id) == {booked.id, free.id}
    assert by_id[booked.id]["is_available"] is False
    assert by_id[free.id]["is_available"] is True


def test_all_slots_available_when_nothing_booked(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    s1 = make_slot(db, plan.id, description="9 AM - 12 PM", sort_order=1)
    s2 = make_slot(db, plan.id, description="1 PM - 4 PM", sort_order=2)
    db.commit()

    resp = client.post(
        f"/api/v1/public/plans/{plan.id}/available-slots",
        headers=_ORIGIN,
        json={"location_id": loc.id, "booking_date": future_date().isoformat()},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert {r["id"] for r in rows} == {s1.id, s2.id}
    assert all(r["is_available"] is True for r in rows)
