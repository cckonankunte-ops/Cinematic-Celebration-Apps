"""Admin location working-hours / cutoff / late-switch management (R5, R6).

The admin catalog router is admin-only, so staff are rejected (403). Admins can
update a location's hours and the late-booking switch, which then affects public
slot availability.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.catalog import list_slots_with_availability
from app.services.slots import ActorKind
from tests.factories import make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login(client: TestClient, username: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def test_staff_cannot_update_location_hours(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    staff = make_user(db, "staff", location_id=loc.id)
    db.commit()
    _login(client, staff.username)

    resp = client.patch(
        f"/api/v1/admin/locations/{loc.id}",
        headers=_ORIGIN,
        json={"allow_late_booking": True},
    )
    assert resp.status_code == 403


def test_admin_updates_hours_and_switch(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin", location_id=None)
    db.commit()
    _login(client, admin.username)

    resp = client.patch(
        f"/api/v1/admin/locations/{loc.id}",
        headers=_ORIGIN,
        json={
            "opens_at": "09:00",
            "closes_at": "23:00",
            "last_online_booking_start": "21:00",
            "allow_late_booking": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["opens_at"].startswith("09:00")
    assert body["closes_at"].startswith("23:00")
    assert body["allow_late_booking"] is True


def test_admin_toggles_booking_mode_repeatedly(client: TestClient, db: Session) -> None:
    loc = make_location(db)  # defaults to booking_mode 'slot'
    admin = make_user(db, "admin", location_id=None)
    db.commit()
    _login(client, admin.username)

    def set_mode(mode: str) -> dict:
        resp = client.patch(
            f"/api/v1/admin/locations/{loc.id}",
            headers=_ORIGIN,
            json={"booking_mode": mode},
        )
        assert resp.status_code == 200
        return resp.json()

    assert set_mode("open")["booking_mode"] == "open"
    assert set_mode("slot")["booking_mode"] == "slot"
    assert set_mode("open")["booking_mode"] == "open"  # flip back and forth freely


def test_invalid_booking_mode_rejected(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin", location_id=None)
    db.commit()
    _login(client, admin.username)

    resp = client.patch(
        f"/api/v1/admin/locations/{loc.id}",
        headers=_ORIGIN,
        json={"booking_mode": "banana"},
    )
    assert resp.status_code == 422  # Literal['slot','open'] rejects it


def test_staff_cannot_change_booking_mode(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    staff = make_user(db, "staff", location_id=loc.id)
    db.commit()
    _login(client, staff.username)

    resp = client.patch(
        f"/api/v1/admin/locations/{loc.id}",
        headers=_ORIGIN,
        json={"booking_mode": "open"},
    )
    assert resp.status_code == 403


def test_switch_affects_same_day_public_availability(
    client: TestClient, db: Session
) -> None:
    """Flipping the late switch toggles SAME-DAY public availability of a late slot.

    The cutoff is same-day only, so its effect is observable for today's date.
    Asserted at the service layer with an injected morning `now` (so the 22:30
    start is still future yet same-day) to stay deterministic — the HTTP
    endpoint can't inject `now`. The admin flips the switch through the API.
    """
    loc = make_location(db)  # cutoff 22:00, switch off
    plan = make_plan(db, loc.id)
    late = make_slot(
        db, plan.id, start_time=time(22, 30), duration_minutes=60, sort_order=1
    )
    admin = make_user(db, "admin", location_id=None)
    db.commit()

    today = date.today()
    now_morning = datetime.combine(today, time(9, 0))

    def late_available() -> bool:
        db.expire_all()  # re-read the location after the admin PATCH commits
        slots = list_slots_with_availability(
            db, plan.id, loc.id, today, actor=ActorKind.PUBLIC, now=now_morning
        )
        return next(s.is_available for s in slots if s.id == late.id)

    assert late_available() is False  # switch off -> hidden same-day

    _login(client, admin.username)
    resp = client.patch(
        f"/api/v1/admin/locations/{loc.id}",
        headers=_ORIGIN,
        json={"allow_late_booking": True},
    )
    assert resp.status_code == 200
    assert late_available() is True  # switch on -> available same-day
