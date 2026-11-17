"""Integration tests for customer-booking-flow-v2 Task 4 endpoints (real PG).

- O1: GET /public/offers returns only safe fields for active+public, in-validity
  coupons; private / inactive / out-of-validity excluded.
- T2: admin disallowed-time create with start >= end -> 422.
- A3: advance-rule CRUD is admin-only — duplicate threshold 409, cross-location
  same threshold allowed, negative values 422, staff/unauth forbidden.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.factories import make_coupon, make_location, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login(client: TestClient, db: Session, role: str, *, location_id=None) -> None:
    make_user(db, role, password="pw-123456", location_id=location_id)
    db.commit()
    from app.models.user import User
    from app.models.user_role import UserRole

    username = db.execute(
        select(User.username)
        .join(UserRole, User.role_id == UserRole.id)
        .where(UserRole.name == role)
        .order_by(User.id.desc())
    ).scalars().first()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


# --- O1: public offers endpoint returns only safe, public, in-validity coupons -
def test_o1_public_offers_safe_fields_only(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    # Public + active + in-validity -> shown. The factory doesn't take the new
    # name/description/is_public fields, so set them on the row after creation.
    from app.models.coupon import Coupon

    make_coupon(db, loc.id, code="PUBLIC10", type="flat", value=10000, is_active=True)
    shown = db.execute(
        select(Coupon).where(Coupon.code == "PUBLIC10")
    ).scalar_one()
    shown.is_public = True
    shown.name = "Flat 100 off"
    shown.description = "Save ₹100 on any booking"
    # Private coupon -> excluded.
    hidden = make_coupon(db, loc.id, code="SECRET", type="flat", value=20000)
    hidden.is_public = False
    # Public but inactive -> excluded.
    inactive = make_coupon(db, loc.id, code="OLD", type="flat", value=5000)
    inactive.is_public = True
    inactive.is_active = False
    db.commit()

    resp = client.get("/api/v1/public/offers")
    assert resp.status_code == 200
    data = resp.json()
    codes = {o["code"] for o in data}
    assert codes == {"PUBLIC10"}
    offer = data[0]
    # Safe fields present (incl. the branch name); internal fields absent.
    assert set(offer.keys()) == {
        "code",
        "name",
        "description",
        "location_name",
        "effective_from",
        "effective_to",
    }
    assert offer["name"] == "Flat 100 off"
    assert offer["location_name"] == loc.name


def test_o1_public_offers_empty_when_none_public(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    c = make_coupon(db, loc.id, code="ONLYPRIV", type="flat", value=10000)
    c.is_public = False
    db.commit()
    resp = client.get("/api/v1/public/offers")
    assert resp.status_code == 200
    assert resp.json() == []


# --- T2: disallowed-time bad range -> 422 -------------------------------------
def test_t2_disallowed_bad_range_rejected(client: TestClient, db: Session) -> None:
    _login(client, db, "admin")
    loc = make_location(db)
    db.commit()
    resp = client.post(
        f"/api/v1/admin/locations/{loc.id}/disallowed-times",
        json={"start_time": "22:00:00", "end_time": "21:00:00"},  # start >= end
        headers=_ORIGIN,
    )
    assert resp.status_code == 422


def test_t2_disallowed_valid_range_created(client: TestClient, db: Session) -> None:
    _login(client, db, "admin")
    loc = make_location(db)
    db.commit()
    resp = client.post(
        f"/api/v1/admin/locations/{loc.id}/disallowed-times",
        json={"start_time": "22:00:00", "end_time": "23:30:00", "note": "no late 1hr"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["location_id"] == loc.id
    assert body["note"] == "no late 1hr"


# --- A3: advance-rule CRUD is admin-only with validation ----------------------
def test_a3_duplicate_threshold_rejected(client: TestClient, db: Session) -> None:
    _login(client, db, "admin")
    loc = make_location(db)
    db.commit()
    body = {"min_total_paise": 100000, "advance_paise": 50000}
    first = client.post(
        f"/api/v1/admin/locations/{loc.id}/advance-rules", json=body, headers=_ORIGIN
    )
    assert first.status_code == 201
    # Same threshold at the same branch -> 409.
    dup = client.post(
        f"/api/v1/admin/locations/{loc.id}/advance-rules", json=body, headers=_ORIGIN
    )
    assert dup.status_code == 409


def test_a3_same_threshold_different_location_allowed(
    client: TestClient, db: Session
) -> None:
    _login(client, db, "admin")
    loc_a = make_location(db, name="A")
    loc_b = make_location(db, name="B")
    db.commit()
    body = {"min_total_paise": 100000, "advance_paise": 50000}
    r_a = client.post(
        f"/api/v1/admin/locations/{loc_a.id}/advance-rules", json=body, headers=_ORIGIN
    )
    r_b = client.post(
        f"/api/v1/admin/locations/{loc_b.id}/advance-rules", json=body, headers=_ORIGIN
    )
    assert r_a.status_code == 201
    assert r_b.status_code == 201


def test_a3_negative_values_rejected(client: TestClient, db: Session) -> None:
    _login(client, db, "admin")
    loc = make_location(db)
    db.commit()
    resp = client.post(
        f"/api/v1/admin/locations/{loc.id}/advance-rules",
        json={"min_total_paise": -1, "advance_paise": 50000},
        headers=_ORIGIN,
    )
    assert resp.status_code == 422


def test_a3_staff_forbidden(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    _login(client, db, "staff", location_id=loc.id)
    db.commit()
    resp = client.post(
        f"/api/v1/admin/locations/{loc.id}/advance-rules",
        json={"min_total_paise": 100000, "advance_paise": 50000},
        headers=_ORIGIN,
    )
    assert resp.status_code == 403


def test_o1_offers_follow_each_branchs_own_validity_window(db: Session) -> None:
    """The same promo at two branches with different windows: on any given day
    only the branches whose window covers that day are returned. (The customer
    page then groups them into one card by code/name/description.)

    Branch1: 15-25 Nov.  Branch2: 17-23 Nov.
    """
    from datetime import date

    from app.services import coupon as coupon_service

    b1 = make_location(db, "Branch1")
    b2 = make_location(db, "Branch2")
    c1 = make_coupon(
        db, b1.id, code="EARLY",
        effective_from=date(2026, 11, 15), effective_to=date(2026, 11, 25),
    )
    c2 = make_coupon(
        db, b2.id, code="EARLY",
        effective_from=date(2026, 11, 17), effective_to=date(2026, 11, 23),
    )
    c1.is_public = True
    c2.is_public = True
    db.commit()

    def branches_on(day: date) -> list[str]:
        return sorted(
            o.location_name for o in coupon_service.list_public_offers(db, on=day)
        )

    both = sorted([b1.name, b2.name])
    assert branches_on(date(2026, 11, 14)) == []          # before either window
    assert branches_on(date(2026, 11, 15)) == [b1.name]   # only branch 1
    assert branches_on(date(2026, 11, 16)) == [b1.name]
    assert branches_on(date(2026, 11, 17)) == both        # both overlap
    assert branches_on(date(2026, 11, 23)) == both        # last day for branch 2
    assert branches_on(date(2026, 11, 24)) == [b1.name]   # branch 2 expired
    assert branches_on(date(2026, 11, 25)) == [b1.name]   # last day for branch 1
    assert branches_on(date(2026, 11, 26)) == []          # both expired
