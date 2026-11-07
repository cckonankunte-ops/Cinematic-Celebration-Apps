"""CLI job: seed the MINIMAL data needed to operate and smoke-test a fresh deploy.

Creates (idempotently):
- the 'admin' and 'staff' user roles (if missing),
- one admin user (username + password from env: SEED_ADMIN_USERNAME /
  SEED_ADMIN_PASSWORD), password stored as an argon2 hash,
- the 3 Bangalore branch locations,
- a minimal bookable catalog (one plan + one slot) at the first location so a
  public booking can be smoke-tested.

Run once on a fresh environment:

    SEED_ADMIN_USERNAME=owner SEED_ADMIN_PASSWORD='<strong>' \
        python -m app.jobs.seed_min

Idempotent: re-running makes no duplicate rows and does NOT change an existing
admin's password. This is the MINIMUM to operate/smoke-test — real production
data is imported by the separate data-migration spec, not here.
"""

from __future__ import annotations

import os
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.location import Location
from app.models.plan import Plan
from app.models.slot import Slot
from app.models.user import User
from app.models.user_role import UserRole

log = get_logger("app.jobs.seed_min")

_ROLES = ("admin", "staff")
_LOCATIONS = (
    ("Hulimavu", "hulimavu"),
    ("Konankunte", "konankunte"),
    ("Electronic City", "electronic-city"),
)
_FAR_PAST = date(2020, 1, 1)


def _ensure_roles(db: Session) -> dict[str, int]:
    """Create the admin/staff roles if missing; return name -> id."""
    ids: dict[str, int] = {}
    for name in _ROLES:
        role = db.execute(
            select(UserRole).where(UserRole.name == name)
        ).scalar_one_or_none()
        if role is None:
            role = UserRole(name=name)
            db.add(role)
            db.flush()
        ids[name] = role.id
    return ids


def _ensure_locations(db: Session) -> list[Location]:
    """Create the 3 branches if missing (keyed by slug); return them in order."""
    out: list[Location] = []
    for name, slug in _LOCATIONS:
        loc = db.execute(
            select(Location).where(Location.slug == slug)
        ).scalar_one_or_none()
        if loc is None:
            loc = Location(name=name, slug=slug, is_active=True)
            db.add(loc)
            db.flush()
        out.append(loc)
    return out


def _ensure_admin(db: Session, admin_role_id: int) -> None:
    """Create one admin user from SEED_ADMIN_* env vars if that username is absent.

    Never changes an existing user's password (idempotent, safe to re-run).
    """
    username = os.environ.get("SEED_ADMIN_USERNAME", "").strip()
    password = os.environ.get("SEED_ADMIN_PASSWORD", "")
    if not username or not password:
        raise SystemExit(
            "SEED_ADMIN_USERNAME and SEED_ADMIN_PASSWORD must be set in the "
            "environment to seed the admin user."
        )
    existing = db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()
    if existing is not None:
        log.info("seed_admin_exists", username=username)
        return
    db.add(
        User(
            username=username,
            password_hash=hash_password(password),  # argon2, never plain text
            role_id=admin_role_id,
            location_id=None,  # admin = all locations
            is_active=True,
        )
    )
    log.info("seed_admin_created", username=username)


def _ensure_min_catalog(db: Session, location: Location) -> None:
    """Create one bookable plan + slot at the given location if none exists."""
    plan = db.execute(
        select(Plan).where(Plan.location_id == location.id)
    ).scalar_one_or_none()
    if plan is None:
        plan = Plan(
            location_id=location.id,
            title="Starter Theatre",
            description="Minimal seed plan for smoke-testing.",
            plan_type=1,
            price_paise=150000,  # ₹1,500
            people_allowed=4,
            max_people_allowed=8,
            extra_guest_paise=15000,  # ₹150/extra guest
            advance_paise=60000,  # ₹600 advance
            effective_from=_FAR_PAST,
        )
        db.add(plan)
        db.flush()
    slot = db.execute(
        select(Slot).where(Slot.plan_id == plan.id)
    ).scalar_one_or_none()
    if slot is None:
        db.add(
            Slot(
                plan_id=plan.id,
                description="5:30 PM - 7:30 PM",
                start_time=time(17, 30),
                duration_minutes=120,
                show_combos=True,
                effective_from=_FAR_PAST,
                sort_order=1,
            )
        )


def seed_min(db: Session) -> None:
    """Idempotently seed roles, admin, locations, and a minimal catalog."""
    role_ids = _ensure_roles(db)
    locations = _ensure_locations(db)
    _ensure_admin(db, role_ids["admin"])
    _ensure_min_catalog(db, locations[0])
    db.commit()
    log.info("seed_min_completed", locations=len(locations))


def main() -> None:
    db = SessionLocal()
    try:
        seed_min(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
