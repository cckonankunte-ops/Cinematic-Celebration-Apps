"""Test factory helpers for seeding the database in tests."""

from __future__ import annotations

import secrets
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.location import Location
from app.models.occasion import Occasion
from app.models.plan import Plan
from app.models.slot import Slot
from app.models.special_decor_item import SpecialDecorItem
from app.models.user import User
from app.models.user_role import UserRole

FAR_PAST = date(2020, 1, 1)
FAR_FUTURE = date(2099, 12, 31)


def ensure_roles(db: Session) -> dict[str, int]:
    """Create 'admin' and 'staff' roles if missing; return name -> id."""
    out: dict[str, int] = {}
    for name in ("admin", "staff"):
        role = db.execute(select(UserRole).where(UserRole.name == name)).scalar_one_or_none()
        if role is None:
            role = UserRole(name=name)
            db.add(role)
            db.flush()
        out[name] = role.id
    return out


def make_location(db: Session, name: str = "Hulimavu", is_active: bool = True) -> Location:
    loc = Location(name=name, slug=f"{name.lower()}-{secrets.token_hex(3)}", is_active=is_active)
    db.add(loc)
    db.flush()
    return loc


def make_user(
    db: Session,
    role: str,
    password: str = "pw-123456",
    location_id: int | None = None,
    is_active: bool = True,
) -> User:
    roles = ensure_roles(db)
    user = User(
        username=f"{role}-{secrets.token_hex(3)}",
        password_hash=hash_password(password),
        role_id=roles[role],
        location_id=location_id,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def make_plan(
    db: Session,
    location_id: int,
    *,
    price_paise: int = 400000,
    people_allowed: int = 4,
    max_people_allowed: int = 10,
    extra_guest_paise: int = 15000,
    give_discount: bool = False,
    max_discount_paise: int = 0,
    advance_paise: int = 50000,
    effective_from: date = FAR_PAST,
    effective_to: date = FAR_FUTURE,
    is_active: bool = True,
) -> Plan:
    plan = Plan(
        location_id=location_id,
        title="Starlight",
        plan_type=1,
        price_paise=price_paise,
        people_allowed=people_allowed,
        max_people_allowed=max_people_allowed,
        extra_guest_paise=extra_guest_paise,
        give_discount=give_discount,
        max_discount_paise=max_discount_paise,
        advance_paise=advance_paise,
        effective_from=effective_from,
        effective_to=effective_to,
        is_active=is_active,
    )
    db.add(plan)
    db.flush()
    return plan


def make_slot(
    db: Session,
    plan_id: int,
    *,
    description: str = "9 AM - 12 PM",
    show_combos: bool = True,
    sort_order: int = 1,
    effective_from: date = FAR_PAST,
    effective_to: date = FAR_FUTURE,
    is_active: bool = True,
) -> Slot:
    slot = Slot(
        plan_id=plan_id,
        description=description,
        show_combos=show_combos,
        sort_order=sort_order,
        effective_from=effective_from,
        effective_to=effective_to,
        is_active=is_active,
    )
    db.add(slot)
    db.flush()
    return slot


def make_cake(
    db: Session, location_id: int, *, price_paise: int = 60000, is_active: bool = True
) -> Cake:
    cake = Cake(
        location_id=location_id,
        description="Chocolate truffle",
        price_paise=price_paise,
        object_key=f"cakes/{secrets.token_hex(3)}.jpg",
        effective_from=FAR_PAST,
        effective_to=FAR_FUTURE,
        is_active=is_active,
    )
    db.add(cake)
    db.flush()
    return cake


def make_decor(
    db: Session, location_id: int, *, price_paise: int = 20000, sort_order: int = 1
) -> SpecialDecorItem:
    decor = SpecialDecorItem(
        location_id=location_id,
        name="Rose bouquet",
        description="A dozen roses",
        price_paise=price_paise,
        object_key=f"decor/{secrets.token_hex(3)}.jpg",
        sort_order=sort_order,
        effective_from=FAR_PAST,
        effective_to=FAR_FUTURE,
    )
    db.add(decor)
    db.flush()
    return decor


def make_combo(db: Session, location_id: int, *, price_paise: int = 30000) -> ComboItem:
    combo = ComboItem(
        location_id=location_id,
        name="Party combo",
        description="Decor + photos",
        price_paise=price_paise,
        object_key=f"combo/{secrets.token_hex(3)}.jpg",
        effective_from=FAR_PAST,
        effective_to=FAR_FUTURE,
    )
    db.add(combo)
    db.flush()
    return combo


def make_occasion(db: Session, location_id: int, name: str = "Birthday") -> Occasion:
    occ = Occasion(location_id=location_id, name=name)
    db.add(occ)
    db.flush()
    return occ


def future_date(days: int = 10) -> date:
    return date.today() + timedelta(days=days)


def make_booking(
    db: Session,
    *,
    location_id: int,
    plan_id: int,
    slot_id: int,
    status: str = "pending",
    total_paise: int = 400000,
    advance_paise: int = 50000,
    booking_date: date | None = None,
    people: int = 4,
):
    """Create a minimal valid booking row for tests."""
    from app.models.booking import Booking

    booking = Booking(
        booking_reference=f"CC-{secrets.token_hex(3)}",
        public_token=secrets.token_urlsafe(12),
        location_id=location_id,
        plan_id=plan_id,
        slot_id=slot_id,
        booking_date=booking_date or future_date(),
        booking_name="Test Customer",
        email="t@example.com",
        people=people,
        plan_price_paise=total_paise,
        subtotal_paise=total_paise,
        total_paise=total_paise,
        advance_paise=advance_paise,
        status=status,
    )
    db.add(booking)
    db.flush()
    return booking
