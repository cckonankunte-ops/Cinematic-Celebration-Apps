"""Admin location working-hours / cutoff / late-switch management (R5, R6).

The admin catalog router is admin-only, so staff are rejected (403). Admins can
update a location's hours and the late-booking switch, which then affects public
slot availability.
"""

from __future__ import annotations

from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import future_date, make_location, make_plan, make_slot, make_user

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


def test_switch_affects_public_availability(client: TestClient, db: Session) -> None:
    loc = make_location(db)  # cutoff 22:00, switch off
    plan = make_plan(db, loc.id)
    late = make_slot(
        db, plan.id, start_time=time(22, 30), duration_minutes=60, sort_order=1
    )
    admin = make_user(db, "admin", location_id=None)
    db.commit()

    when = future_date().isoformat()

    def late_available() -> bool:
        resp = client.post(
            f"/api/v1/public/plans/{plan.id}/available-slots",
            headers=_ORIGIN,
            json={"location_id": loc.id, "booking_date": when},
        )
        assert resp.status_code == 200
        return next(s["is_available"] for s in resp.json() if s["id"] == late.id)

    assert late_available() is False  # switch off -> hidden

    _login(client, admin.username)
    client.patch(
        f"/api/v1/admin/locations/{loc.id}",
        headers=_ORIGIN,
        json={"allow_late_booking": True},
    )
    assert late_available() is True  # switch on -> available
