"""Integration test — preview equals save (real PostgreSQL).

Feature: admin-booking-edit, Property 13: Preview equals save. A preview and a
save built from identical inputs (cake + weight, decor quantities, a combo with
a cake baseline, LED, and a flat coupon) produce identical money: the persisted
booking's subtotal, total, discount, coupon discount, and coupon code match the
preview breakdown exactly.

Validates: Requirements 6.1, 7.1, 7.3
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.schemas.booking import (
    AdminBookingCreate,
    AdminPreviewRequest,
    ComboSelectionIn,
    DecorSelectionIn,
)
from app.services import booking as booking_service
from tests.factories import (
    future_date,
    make_cake,
    make_combo,
    make_coupon,
    make_decor,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration


def test_admin_preview_equals_persisted_save(db: Session) -> None:
    """The admin preview breakdown equals the booking persisted by create."""
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
    # Combo with a cake baseline so the cake is priced THROUGH the combo delta.
    combo = make_combo(db, loc.id, price_paise=30000, cake_baseline_paise=50000)
    make_coupon(db, loc.id, code="FLAT100", type="flat", value=10000)
    db.flush()

    admin = make_user(db, "admin", location_id=None)
    db.flush()
    admin_cu = CurrentUser(
        id=admin.id, username=admin.username, role="admin", location_id=None
    )

    booking_date = future_date()

    # Identical inputs for the preview and the save.
    shared = dict(
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=booking_date,
        people=5,
        cake_id=cake.id,
        cake_weight_half_kg=3,
        special_decor=[DecorSelectionIn(id=decor.id, quantity=2)],
        combos=[ComboSelectionIn(id=combo.id)],
        led_name="HAPPY",
        coupon_code="FLAT100",
        discount_paise=10000,
    )

    preview_req = AdminPreviewRequest(**shared)
    create_req = AdminBookingCreate(
        booking_name="Preview Save",
        phone="9876543210",
        email="save@example.com",
        **shared,
    )

    preview = booking_service.preview_booking(
        db, preview_req, actor=admin_cu, is_customer=False
    )
    booking = booking_service.create_admin_booking(db, create_req, admin_cu)

    assert booking.subtotal_paise == preview.subtotal_paise
    assert booking.total_paise == preview.total_paise
    assert booking.discount_paise == preview.discount_paise
    assert booking.coupon_discount_paise == preview.coupon_discount_paise
    assert booking.coupon_code == preview.coupon_code
