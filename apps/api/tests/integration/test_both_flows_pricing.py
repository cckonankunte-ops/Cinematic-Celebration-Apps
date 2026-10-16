"""Integration test — both flows apply identical pricing (real PostgreSQL).

Feature: admin-booking-edit, Property 10: Both flows apply identical pricing.
The public and admin preview paths share the same server-authoritative
``compute_booking_price``: given identical items/quantities/cake weight/LED,
the add-on subtotal is identical. The customer flow forces the manual discount
to 0 (``is_customer=True``) while the admin flow applies the plan's allowed
discount; the public HTTP path accepts no admin money fields.

Validates: Requirements 12.6, 16.8, 17.4
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.schemas.booking import (
    AdminPreviewRequest,
    ComboSelectionIn,
    DecorSelectionIn,
    PublicPreviewRequest,
)
from app.services import booking as booking_service
from tests.factories import (
    future_date,
    make_cake,
    make_combo,
    make_decor,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}
_ADMIN_DISCOUNT = 30000


def _seed(db: Session):
    loc = make_location(db)
    plan = make_plan(
        db,
        loc.id,
        max_people_allowed=10,
        give_discount=True,
        max_discount_paise=50000,
    )
    slot = make_slot(db, plan.id)
    cake = make_cake(db, loc.id, price_paise=60000)
    decor = make_decor(db, loc.id, price_paise=20000)
    combo = make_combo(db, loc.id, price_paise=30000)
    db.flush()
    return loc, plan, slot, cake, decor, combo


def test_public_and_admin_previews_share_subtotal_and_discount_differs(
    db: Session,
) -> None:
    """Same items -> same subtotal; customer discount 0, admin discount applied."""
    loc, plan, slot, cake, decor, combo = _seed(db)
    admin = make_user(db, "admin", location_id=None)
    db.flush()
    admin_cu = CurrentUser(
        id=admin.id, username=admin.username, role="admin", location_id=None
    )

    booking_date = future_date()
    shared = dict(
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=booking_date,
        people=5,
        cake_id=cake.id,
        cake_weight_half_kg=2,
        special_decor=[DecorSelectionIn(id=decor.id, quantity=2)],
        combos=[ComboSelectionIn(id=combo.id)],
        led_name="HELLO",
    )

    public_req = PublicPreviewRequest(**shared)
    admin_req = AdminPreviewRequest(discount_paise=_ADMIN_DISCOUNT, **shared)

    public_preview = booking_service.preview_booking(db, public_req, is_customer=True)
    admin_preview = booking_service.preview_booking(
        db, admin_req, actor=admin_cu, is_customer=False
    )

    # Customer discount is forced to 0; admin discount reflects the plan's allowance.
    assert public_preview.discount_paise == 0
    assert admin_preview.discount_paise == _ADMIN_DISCOUNT

    # Same add-on/subtotal portions prove both flows use compute_booking_price.
    assert public_preview.subtotal_paise == admin_preview.subtotal_paise
    assert public_preview.plan_price_paise == admin_preview.plan_price_paise
    assert public_preview.extra_guest_paise == admin_preview.extra_guest_paise


def test_public_preview_endpoint_ignores_admin_money_fields(
    client: TestClient, db: Session
) -> None:
    """POSTing the public preview returns 200 and the same subtotal; no admin money.

    The public endpoint parses ``PublicPreviewRequest`` which has no money
    fields, so a sneaked-in ``discount_paise`` is simply dropped and the
    discount stays 0 — confirming the public path cannot apply a manual discount.
    """
    loc, plan, slot, cake, decor, combo = _seed(db)
    db.commit()

    booking_date = future_date()
    body = {
        "location_id": loc.id,
        "plan_id": plan.id,
        "slot_id": slot.id,
        "booking_date": booking_date.isoformat(),
        "people": 5,
        "cake_id": cake.id,
        "cake_weight_half_kg": 2,
        "special_decor": [{"id": decor.id, "quantity": 2}],
        "combos": [{"id": combo.id}],
        "led_name": "HELLO",
        # Admin-only money field is not part of PublicPreviewRequest; it is ignored.
        "discount_paise": _ADMIN_DISCOUNT,
    }

    resp = client.post("/api/v1/public/bookings/preview", json=body, headers=_ORIGIN)
    assert resp.status_code == 200
    data = resp.json()
    assert data["discount_paise"] == 0

    # The subtotal matches the service-layer public preview for the same inputs.
    public_req = PublicPreviewRequest(
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=booking_date,
        people=5,
        cake_id=cake.id,
        cake_weight_half_kg=2,
        special_decor=[DecorSelectionIn(id=decor.id, quantity=2)],
        combos=[ComboSelectionIn(id=combo.id)],
        led_name="HELLO",
    )
    expected = booking_service.preview_booking(db, public_req, is_customer=True)
    assert data["subtotal_paise"] == expected.subtotal_paise
