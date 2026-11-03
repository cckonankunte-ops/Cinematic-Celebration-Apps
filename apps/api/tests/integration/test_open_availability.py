"""Open-mode availability generation (service-level + endpoint smoke).

Generates candidate :00/:30 start times across a location's working hours for a
chosen duration, flagging each available/unavailable by the same time-rule
pipeline + overlap/buffer logic used everywhere else. The service is driven
directly so `now` is injectable (deterministic); a public-endpoint smoke test
confirms wiring.
"""

from __future__ import annotations

from datetime import datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.plan_pricing import PlanPricing
from app.services.catalog import generate_open_availability
from app.services.slots import ActorKind
from tests.factories import FAR_FUTURE, FAR_PAST, future_date, make_location, make_plan

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _open_location(db: Session) -> object:
    loc = make_location(db)  # opens 10:00, closes 01:00 (next day)
    loc.booking_mode = "open"
    return loc


def _price_duration(db: Session, plan_id: int, duration: int) -> None:
    db.add(
        PlanPricing(
            plan_id=plan_id,
            duration_minutes=duration,
            price_paise=100000,
            advance_paise=0,
            effective_from=FAR_PAST,
            effective_to=FAR_FUTURE,
            is_active=True,
        )
    )


def test_generates_half_hour_starts_within_hours(db: Session) -> None:
    loc = _open_location(db)
    plan = make_plan(db, loc.id)
    _price_duration(db, plan.id, 60)
    db.commit()

    # now before the day so every same-day start is in the future.
    on = future_date()
    now = datetime.combine(on, time(0, 0))
    result = generate_open_availability(
        db, plan.id, loc.id, on, 60, actor=ActorKind.PUBLIC, now=now
    )
    starts = [r.start_time for r in result]
    # Opens 10:00; 1h slots; last start whose usable end <= 01:00 next day is 00:00.
    assert time(10, 0) in starts
    assert time(10, 30) in starts
    assert all(s.minute in (0, 30) for s in starts)
    # Every generated start is available (nothing booked).
    assert all(r.is_available for r in result)


def test_held_window_blocks_overlapping_starts(db: Session) -> None:
    loc = _open_location(db)
    plan = make_plan(db, loc.id)
    _price_duration(db, plan.id, 60)
    on = future_date()
    # An active open-mode booking 15:00–16:00 (buffer 30 → occupies until 16:30).
    db.add(
        Booking(
            booking_reference="CC-OPEN-HELD-0001",
            public_token="held-token-0001",
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=None,
            booking_date=on,
            start_time=time(15, 0),
            duration_minutes=60,
            booking_name="Held",
            people=2,
            plan_price_paise=100000,
            extra_guest_paise=0,
            subtotal_paise=100000,
            total_paise=100000,
            status="accepted",
        )
    )
    db.commit()

    now = datetime.combine(on, time(0, 0))
    by_start = {
        r.start_time: r.is_available
        for r in generate_open_availability(
            db, plan.id, loc.id, on, 60, actor=ActorKind.PUBLIC, now=now
        )
    }
    assert by_start[time(15, 0)] is False  # the held start itself
    assert by_start[time(15, 30)] is False  # overlaps the held window
    assert by_start[time(16, 0)] is False  # within the 30-min buffer
    assert by_start[time(16, 30)] is True  # back-to-back at the buffer boundary


def test_endpoint_returns_availability(client: TestClient, db: Session) -> None:
    loc = _open_location(db)
    plan = make_plan(db, loc.id)
    _price_duration(db, plan.id, 60)
    db.commit()

    resp = client.post(
        f"/api/v1/public/plans/{plan.id}/open-availability",
        headers=_ORIGIN,
        json={
            "location_id": loc.id,
            "booking_date": future_date().isoformat(),
            "duration_minutes": 60,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert {"start_time", "is_available"} <= set(body[0])
