"""Analytics reports (real PG): slot amounts, bookings created, today income.

Rules under test:
- Slot amounts select bookings by CELEBRATION date and count ALL of their
  payments, whenever received.
- Default status filter is accepted only; others are opt-in.
- Today income counts payments by received date (IST), net of reversals.
- Bookings created selects by created_at (IST) and lists cake/decor/combos.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.booking_item import BookingItem
from app.models.payment import Payment
from tests.factories import (
    make_booking,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login(client: TestClient, username: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def _pay(db: Session, booking_id: int, method: str, paise: int, at: datetime) -> None:
    db.add(
        Payment(booking_id=booking_id, method=method, amount_paise=paise, received_at=at)
    )
    db.flush()


def _seed(db: Session):
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    admin = make_user(db, "admin", password="pw-123456", location_id=None)
    return loc, plan, slot, admin


def _booking(db, loc, plan, slot, day: date, status: str = "accepted", total: int = 400000):
    return make_booking(
        db,
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=day,
        status=status,
        total_paise=total,
    )


def test_slot_amounts_uses_celebration_date_and_all_payments(
    client: TestClient, db: Session
) -> None:
    loc, plan, slot, admin = _seed(db)
    inside = _booking(db, loc, plan, slot, date(2099, 11, 21))
    outside = _booking(db, loc, plan, slot, date(2099, 11, 30))
    # Advance received well BEFORE the range, balance on the day.
    _pay(db, inside.id, "upi", 50000, datetime(2099, 11, 15, 6, 0, tzinfo=UTC))
    _pay(db, inside.id, "cash", 100000, datetime(2099, 11, 21, 6, 0, tzinfo=UTC))
    _pay(db, outside.id, "upi", 10000, datetime(2099, 11, 21, 6, 0, tzinfo=UTC))
    db.commit()
    _login(client, admin.username)

    resp = client.get(
        f"/api/v1/admin/analytics/slot-amounts?location_id={loc.id}"
        "&date_from=2099-11-18&date_to=2099-11-24"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [r["booking_reference"] for r in body["rows"]] == [inside.booking_reference]
    row = body["rows"][0]
    assert row["amount_paid_paise"] == 150000
    assert row["paid_by_method"] == {"upi": 50000, "cash": 100000}
    assert row["amount_due_paise"] == 250000
    assert body["summary"]["booking_count"] == 1
    assert body["summary"]["paid_by_method"] == {"upi": 50000, "cash": 100000}


def test_status_filter_defaults_to_accepted(client: TestClient, db: Session) -> None:
    loc, plan, slot, admin = _seed(db)
    accepted = _booking(db, loc, plan, slot, date(2099, 11, 21))
    _booking(db, loc, plan, make_slot(db, plan.id), date(2099, 11, 21), status="pending")
    db.commit()
    _login(client, admin.username)

    base = f"/api/v1/admin/analytics/slot-amounts?location_id={loc.id}&date=2099-11-21"
    default = client.get(base).json()
    assert [r["booking_reference"] for r in default["rows"]] == [accepted.booking_reference]

    both = client.get(base + "&status=accepted&status=pending").json()
    assert len(both["rows"]) == 2


def test_today_income_counts_received_date_net_of_reversals(
    client: TestClient, db: Session
) -> None:
    loc, plan, slot, admin = _seed(db)
    b = _booking(db, loc, plan, slot, date(2099, 12, 25))
    _pay(db, b.id, "upi", 50000, datetime(2099, 11, 15, 6, 0, tzinfo=UTC))  # earlier day
    _pay(db, b.id, "cash", 30000, datetime(2099, 11, 21, 6, 0, tzinfo=UTC))
    _pay(db, b.id, "cash", -5000, datetime(2099, 11, 21, 7, 0, tzinfo=UTC))  # reversal
    # 2099-11-20 19:00 UTC == 2099-11-21 00:30 IST -> counts as the 21st in IST.
    _pay(db, b.id, "card", 20000, datetime(2099, 11, 20, 19, 0, tzinfo=UTC))
    db.commit()
    _login(client, admin.username)

    resp = client.get(
        f"/api/v1/admin/analytics/today-income?location_id={loc.id}&date=2099-11-21"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["received_by_method"] == {"cash": 25000, "card": 20000}
    assert row["received_paise"] == 45000
    assert row["amount_paid_paise"] == 95000  # includes the earlier UPI advance
    assert body["summary"]["payment_count"] == 3
    assert body["summary"]["received_paise"] == 45000

    other_day = client.get(
        f"/api/v1/admin/analytics/today-income?location_id={loc.id}&date=2099-11-20"
    ).json()
    assert other_day["rows"] == []


def test_today_income_includes_cancelled_booking_money(
    client: TestClient, db: Session
) -> None:
    loc, plan, slot, admin = _seed(db)
    b = _booking(db, loc, plan, slot, date(2099, 12, 25), status="cancelled")
    _pay(db, b.id, "upi", 40000, datetime(2099, 11, 21, 6, 0, tzinfo=UTC))
    db.commit()
    _login(client, admin.username)

    body = client.get(
        f"/api/v1/admin/analytics/today-income?location_id={loc.id}&date=2099-11-21"
    ).json()
    assert [r["status"] for r in body["rows"]] == ["cancelled"]
    only_accepted = client.get(
        f"/api/v1/admin/analytics/today-income?location_id={loc.id}"
        "&date=2099-11-21&status=accepted"
    ).json()
    assert only_accepted["rows"] == []


def test_created_bookings_by_created_date_with_addons(
    client: TestClient, db: Session
) -> None:
    loc, plan, slot, admin = _seed(db)
    b = _booking(db, loc, plan, slot, date(2099, 12, 25))
    # 2099-11-21 19:00 UTC == 2099-11-22 00:30 IST.
    b.created_at = datetime(2099, 11, 21, 19, 0, tzinfo=UTC)
    db.add_all(
        [
            BookingItem(booking_id=b.id, kind="cake", name_snapshot="Truffle",
                        price_paise=50000, quantity=1, weight_half_kg=2),
            BookingItem(booking_id=b.id, kind="decor", name_snapshot="Balloons",
                        price_paise=20000, quantity=2),
            BookingItem(booking_id=b.id, kind="combo", name_snapshot="Snacks",
                        price_paise=30000, quantity=1),
        ]
    )
    _pay(db, b.id, "upi", 50000, datetime(2099, 11, 22, 6, 0, tzinfo=UTC))
    db.commit()
    _login(client, admin.username)

    base = f"/api/v1/admin/analytics/created-bookings?location_id={loc.id}"
    on_22 = client.get(base + "&date=2099-11-22").json()
    assert len(on_22["rows"]) == 1
    row = on_22["rows"][0]
    assert row["booking_date"] == "2099-12-25"
    assert row["plan_title"] == plan.title
    assert row["cake"] == "Truffle (1 kg)"
    assert row["special_decor"] == ["Balloons ×2"]
    assert row["combos"] == ["Snacks"]
    assert row["amount_due_paise"] == 350000
    # Created at 00:30 IST on the 22nd, so the 21st (IST) must not include it.
    assert client.get(base + "&date=2099-11-21").json()["rows"] == []


def test_range_validation_and_admin_only(client: TestClient, db: Session) -> None:
    loc, plan, slot, admin = _seed(db)
    staff = make_user(db, "staff", password="pw-123456", location_id=loc.id)
    db.commit()

    _login(client, staff.username)
    assert (
        client.get(
            f"/api/v1/admin/analytics/slot-amounts?location_id={loc.id}&date=2099-11-21"
        ).status_code
        == 403
    )

    _login(client, admin.username)
    inverted = client.get(
        f"/api/v1/admin/analytics/slot-amounts?location_id={loc.id}"
        "&date_from=2099-11-24&date_to=2099-11-18"
    )
    assert inverted.status_code == 422
    too_wide = client.get(
        f"/api/v1/admin/analytics/slot-amounts?location_id={loc.id}"
        "&date_from=2098-01-01&date_to=2099-12-31"
    )
    assert too_wide.status_code == 422
    assert (
        client.get(
            f"/api/v1/admin/analytics/slot-amounts/export?location_id={loc.id}"
            "&date_from=2099-11-18&date_to=2099-11-24"
        ).status_code
        == 200
    )
