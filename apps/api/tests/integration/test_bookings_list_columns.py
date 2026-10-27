"""Admin bookings list carries the main columns from the legacy grid.

GET /api/v1/admin/bookings returns each booking with the plan/slot/occasion
labels, the special-person name, the discount, the special-decor and cake
names, and the created-at timestamp — alongside the reference, guests, and the
derived payment amounts. This test creates a booking with a cake, decor, and
occasion via the admin create endpoint and asserts the list row is populated.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    future_date,
    make_cake,
    make_decor,
    make_location,
    make_occasion,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def test_list_includes_main_columns(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id, description="9 AM - 12 PM")
    cake = make_cake(db, loc.id)
    decor = make_decor(db, loc.id)
    occasion = make_occasion(db, loc.id, name="Anniversary")
    admin = make_user(db, "admin", location_id=None)
    db.commit()

    client.post(
        "/api/v1/auth/login",
        json={"username": admin.username, "password": "pw-123456"},
        headers=_ORIGIN,
    )

    create = client.post(
        "/api/v1/admin/bookings",
        headers=_ORIGIN,
        json={
            "location_id": loc.id,
            "plan_id": plan.id,
            "slot_id": slot.id,
            "booking_date": future_date().isoformat(),
            "booking_name": "Priya S",
            "phone": "9876543210",
            "special_person_name": "Arjun",
            "people": 4,
            "occasion_id": occasion.id,
            "cake_id": cake.id,
            "cake_weight_half_kg": 2,
            "special_decor": [{"id": decor.id, "quantity": 1}],
            "combos": [],
            "discount_paise": 10000,
        },
    )
    assert create.status_code == 201

    resp = client.get(
        f"/api/v1/admin/bookings?location_id={loc.id}", headers=_ORIGIN
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]

    assert row["plan_title"] == plan.title
    assert row["slot_description"] == "9 AM - 12 PM"
    assert row["occasion_name"] == "Anniversary"
    assert row["special_person_name"] == "Arjun"
    assert row["discount_paise"] == 10000
    assert cake.description in row["cakes"]
    assert decor.name in row["special_decor"]
    assert "created_at" in row and row["created_at"]
    # Derived payment amounts still present.
    assert row["amount_due_paise"] == row["total_paise"] - row["amount_paid_paise"]
