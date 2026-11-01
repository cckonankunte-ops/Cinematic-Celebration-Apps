"""Admin slot (time-range) + per-duration pricing CRUD (R1, R2, R5, R11).

Drives the admin catalog endpoints:
- slot create validates :00/:30 start, duration > 0, and working-hours
  containment;
- plan-pricing create/list enforces one active row per (plan, duration).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_location, make_plan, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login_admin(client: TestClient, db: Session):
    admin = make_user(db, "admin", location_id=None)
    db.commit()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def _slot_body(plan_id: int, **over: object) -> dict:
    body = {
        "plan_id": plan_id,
        "start_time": "15:00",
        "duration_minutes": 60,
        "effective_from": "2020-01-01",
    }
    body.update(over)
    return body


def test_create_slot_valid(client: TestClient, db: Session) -> None:
    loc = make_location(db)  # defaults: opens 10:00, closes 01:00
    plan = make_plan(db, loc.id)
    db.commit()
    _login_admin(client, db)

    resp = client.post(
        "/api/v1/admin/slots", json=_slot_body(plan.id), headers=_ORIGIN
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["start_time"].startswith("15:00")
    assert body["duration_minutes"] == 60
    # Derived label when no description supplied.
    assert body["description"] == "3:00 PM - 4:00 PM"


@pytest.mark.parametrize("bad_start", ["15:15", "15:45"])
def test_create_slot_rejects_non_half_hour(
    client: TestClient, db: Session, bad_start: str
) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    db.commit()
    _login_admin(client, db)

    resp = client.post(
        "/api/v1/admin/slots",
        json=_slot_body(plan.id, start_time=bad_start),
        headers=_ORIGIN,
    )
    assert resp.status_code == 422


def test_create_slot_rejects_outside_working_hours(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)  # closes 01:00
    plan = make_plan(db, loc.id)
    db.commit()
    _login_admin(client, db)

    # 02:00 start is outside 10:00-01:00.
    resp = client.post(
        "/api/v1/admin/slots",
        json=_slot_body(plan.id, start_time="02:00", duration_minutes=60),
        headers=_ORIGIN,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "OUTSIDE_WORKING_HOURS"


def test_plan_pricing_crud_and_unique_pair(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    db.commit()
    _login_admin(client, db)

    def pricing(duration: int, price: int) -> dict:
        return {
            "plan_id": plan.id,
            "duration_minutes": duration,
            "price_paise": price,
            "advance_paise": 50000,
            "effective_from": "2020-01-01",
        }

    # Create 1h and 2h prices.
    r1 = client.post("/api/v1/admin/plan-pricing", json=pricing(60, 79900), headers=_ORIGIN)
    assert r1.status_code == 201
    r2 = client.post("/api/v1/admin/plan-pricing", json=pricing(120, 119900), headers=_ORIGIN)
    assert r2.status_code == 201

    # Duplicate active (plan, 60) rejected.
    dup = client.post("/api/v1/admin/plan-pricing", json=pricing(60, 88800), headers=_ORIGIN)
    assert dup.status_code == 422

    # List returns both, ordered by duration.
    listed = client.get(
        f"/api/v1/admin/plan-pricing?plan_id={plan.id}", headers=_ORIGIN
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert [r["duration_minutes"] for r in rows] == [60, 120]
    assert [r["price_paise"] for r in rows] == [79900, 119900]
