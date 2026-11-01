"""Slot availability flagging for the booking UIs (time-range model).

POST /api/v1/public/plans/{id}/available-slots returns ALL active slots for the
plan/date, each annotated with `is_available`. A slot is unavailable when its
occupied window (incl. the cleaning buffer) overlaps an active booking, or when
it fails a public time rule (working-hours, future-start, late cutoff). Held/
blocked slots are returned (not hidden) so the UI can grey them out.
"""

from __future__ import annotations

from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import future_date, make_location, make_plan, make_slot

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _avail(client: TestClient, plan_id: int, loc_id: int, when: str) -> dict:
    resp = client.post(
        f"/api/v1/public/plans/{plan_id}/available-slots",
        headers=_ORIGIN,
        json={"location_id": loc_id, "booking_date": when},
    )
    assert resp.status_code == 200
    return {s["id"]: s for s in resp.json()}


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


def test_held_window_flags_overlapping_slot_unavailable(
    client: TestClient, db: Session
) -> None:
    """Booking a 3-4 PM slot (buffer 30) blocks a 4:00 PM slot but not 4:30 PM."""
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    booked = make_slot(
        db, plan.id, description="3-4 PM", start_time=time(15, 0),
        duration_minutes=60, sort_order=1,
    )
    inside_buffer = make_slot(
        db, plan.id, description="4-5 PM", start_time=time(16, 0),
        duration_minutes=60, sort_order=2,
    )
    after_buffer = make_slot(
        db, plan.id, description="4:30-5:30 PM", start_time=time(16, 30),
        duration_minutes=60, sort_order=3,
    )
    db.commit()

    when = future_date().isoformat()
    _book(client, loc.id, plan.id, booked.id, when)

    by_id = _avail(client, plan.id, loc.id, when)
    assert set(by_id) == {booked.id, inside_buffer.id, after_buffer.id}
    assert by_id[booked.id]["is_available"] is False  # itself held
    assert by_id[inside_buffer.id]["is_available"] is False  # within 30-min buffer
    assert by_id[after_buffer.id]["is_available"] is True  # back-to-back at buffer


def test_all_slots_available_when_nothing_booked(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    s1 = make_slot(
        db, plan.id, start_time=time(11, 0), duration_minutes=60, sort_order=1
    )
    s2 = make_slot(
        db, plan.id, start_time=time(13, 0), duration_minutes=60, sort_order=2
    )
    db.commit()

    by_id = _avail(client, plan.id, loc.id, future_date().isoformat())
    assert {s1.id, s2.id} <= set(by_id)
    assert by_id[s1.id]["is_available"] is True
    assert by_id[s2.id]["is_available"] is True


def test_post_cutoff_slot_unavailable_to_public_when_switch_off(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)  # cutoff 22:00, allow_late_booking False
    plan = make_plan(db, loc.id)
    late = make_slot(
        db, plan.id, start_time=time(22, 30), duration_minutes=60, sort_order=1
    )
    db.commit()

    by_id = _avail(client, plan.id, loc.id, future_date().isoformat())
    assert by_id[late.id]["is_available"] is False


def test_post_cutoff_slot_available_to_public_when_switch_on(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    loc.allow_late_booking = True
    plan = make_plan(db, loc.id)
    late = make_slot(
        db, plan.id, start_time=time(22, 30), duration_minutes=60, sort_order=1
    )
    db.commit()

    by_id = _avail(client, plan.id, loc.id, future_date().isoformat())
    assert by_id[late.id]["is_available"] is True
