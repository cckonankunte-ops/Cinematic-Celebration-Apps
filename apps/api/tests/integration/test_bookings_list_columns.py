"""Admin bookings list carries the main columns from the legacy grid.

GET /api/v1/admin/bookings returns each booking with the plan/slot/occasion
labels, the special-person name, the discount, the special-decor and cake
names, and the created-at timestamp — alongside the reference, guests, and the
derived payment amounts, plus the WhatsApp-confirmation fields (name on cake,
cake weight, LED name, and the location map URL). This test creates a booking
with a cake, decor, combo, and occasion via the admin create endpoint and
asserts the list row is populated.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    future_date,
    make_cake,
    make_combo,
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
    loc.map_url = "https://maps.app.goo.gl/example"
    # Allow an admin manual discount so the requested 10000 isn't clamped to 0
    # (server clamps admin discount to [0, plan.max_discount_paise], 0 when the
    # plan disallows discounts).
    plan = make_plan(db, loc.id, give_discount=True, max_discount_paise=50000)
    slot = make_slot(db, plan.id, description="9 AM - 12 PM")
    cake = make_cake(db, loc.id)
    decor = make_decor(db, loc.id)
    combo = make_combo(db, loc.id)
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
            "name_on_cake": "Happy Birthday",
            "people": 4,
            "occasion_id": occasion.id,
            "cake_id": cake.id,
            "cake_weight_half_kg": 2,
            "special_decor": [{"id": decor.id, "quantity": 1}],
            "combos": [{"id": combo.id}],
            "discount_paise": 10000,
        },
    )
    assert create.status_code == 201
    reference = create.json()["booking_reference"]

    resp = client.get(
        f"/api/v1/admin/bookings?location_id={loc.id}", headers=_ORIGIN
    )
    assert resp.status_code == 200
    rows = resp.json()
    # Select this test's own booking by reference rather than assuming a single
    # row, so the test is robust whether the DB is empty or pre-populated.
    matches = [r for r in rows if r["booking_reference"] == reference]
    assert len(matches) == 1
    row = matches[0]

    assert row["plan_title"] == plan.title
    assert row["slot_description"] == "9 AM - 12 PM"
    assert row["occasion_name"] == "Anniversary"
    assert row["special_person_name"] == "Arjun"
    assert row["discount_paise"] == 10000
    assert cake.description in row["cakes"]
    assert decor.name in row["special_decor"]
    assert combo.name in row["combos"]
    assert "created_at" in row and row["created_at"]
    # WhatsApp-confirmation fields.
    assert row["name_on_cake"] == "Happy Birthday"
    assert row["cake_weight_half_kg"] == 2
    assert row["map_url"] == "https://maps.app.goo.gl/example"
    # Derived payment amounts are present on the row.
    assert "amount_paid_paise" in row
    assert "amount_due_paise" in row
    assert "total_paise" in row
