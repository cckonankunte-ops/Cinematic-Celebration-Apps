"""Edit round-trip for a combo-absorbed cake (real Postgres).

Regression: when a combo absorbs the cake (the cake's cost is carried by the
combo's cake upgrade, not a standalone cake line), the chosen cake id + weight
must still be persisted so an edit can reconstruct the selection. Previously the
absorbed cake was stored nowhere, so editing the booking silently dropped the
combo's cake upgrade and shrank the combo/subtotal/total.

The fix records a 0-amount ``kind='cake'`` line flagged ``absorbed_by_combo``;
this test proves an unrelated edit (change people) preserves the combo amount
and the totals.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.schemas.booking import AdminBookingCreate, BookingUpdate, ComboSelectionIn
from app.services import booking as booking_service
from tests.factories import (
    future_date,
    make_cake,
    make_combo,
    make_location,
    make_plan,
    make_slot,
    make_user,
)

pytestmark = pytest.mark.integration


def _admin(db: Session) -> CurrentUser:
    user = make_user(db, "admin", location_id=None)
    return CurrentUser(
        id=user.id, username=user.username, role="admin", location_id=None
    )


def test_edit_preserves_combo_absorbed_cake(db: Session) -> None:
    """Editing a booking with a combo-absorbed cake keeps the cake upgrade."""
    admin = _admin(db)
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    # Cake weighted 60000 @ 0.5kg; combo base 30000 with a 50000 cake baseline.
    # cake_upgrade = max(0, 60000 - 50000) = 10000 -> combo line = 40000.
    cake = make_cake(db, loc.id, price_paise=60000)
    combo = make_combo(db, loc.id, price_paise=30000, cake_baseline_paise=50000)
    db.commit()

    when = future_date()
    create = AdminBookingCreate(
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=when,
        booking_name="Combo Cake",
        phone="9876543210",
        email="cc@example.com",
        people=2,
        cake_id=cake.id,
        cake_weight_half_kg=1,
        special_decor=[],
        combos=[ComboSelectionIn(id=combo.id)],
    )
    booking = booking_service.create_admin_booking(db, create, admin)

    original_subtotal = booking.subtotal_paise
    original_total = booking.total_paise

    # The absorbed cake is persisted as a 0-amount cake line for round-trip.
    from app.models.booking_item import BookingItem

    items = (
        db.query(BookingItem).filter(BookingItem.booking_id == booking.id).all()
    )
    cake_items = [it for it in items if it.kind == "cake"]
    combo_items = [it for it in items if it.kind == "combo"]
    assert len(cake_items) == 1
    assert cake_items[0].item_id == cake.id
    assert cake_items[0].weight_half_kg == 1
    assert cake_items[0].price_paise == 0  # absorbed -> contributes nothing
    assert len(combo_items) == 1
    assert combo_items[0].price_paise == 40000  # 30000 base + 10000 cake upgrade

    # Edit something unrelated (people). The combo's cake upgrade must survive,
    # so subtotal/total are unchanged (people 2 is within the plan allowance).
    updated = booking_service.update_booking(
        db, booking.id, BookingUpdate(people=3), admin
    )
    assert updated.people == 3
    assert updated.subtotal_paise == original_subtotal
    assert updated.total_paise == original_total

    db.refresh(booking)
    items_after = (
        db.query(BookingItem).filter(BookingItem.booking_id == booking.id).all()
    )
    combo_after = [it for it in items_after if it.kind == "combo"]
    cake_after = [it for it in items_after if it.kind == "cake"]
    assert len(combo_after) == 1
    assert combo_after[0].price_paise == 40000  # upgrade retained, not dropped
    assert len(cake_after) == 1
    assert cake_after[0].item_id == cake.id
    assert cake_after[0].weight_half_kg == 1
