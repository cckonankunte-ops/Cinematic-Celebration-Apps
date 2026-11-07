"""Minimal-seed job: idempotency + argon2 password hashing (real Postgres).

Verifies the deploy seed (app.jobs.seed_min.seed_min):
- creates roles, 3 locations, one admin, and a minimal bookable catalog;
- stores the admin password as an argon2 hash (never plain text);
- is idempotent — a second run adds no duplicates and does not change the
  admin's password.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jobs.seed_min import seed_min
from app.models.location import Location
from app.models.plan import Plan
from app.models.slot import Slot
from app.models.user import User

pytestmark = pytest.mark.integration

_PASSWORD = "seed-pw-123456"


def _count(db: Session, model) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


def test_seed_min_creates_and_is_idempotent(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEED_ADMIN_USERNAME", "owner")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", _PASSWORD)

    seed_min(db)

    # 3 locations, 1 admin, >=1 plan + slot.
    assert _count(db, Location) == 3
    assert _count(db, User) == 1
    assert _count(db, Plan) >= 1
    assert _count(db, Slot) >= 1

    admin = db.execute(select(User).where(User.username == "owner")).scalar_one()
    # Password stored as an argon2 hash, never plain text.
    assert admin.password_hash != _PASSWORD
    assert admin.password_hash.startswith("$argon2")
    assert admin.location_id is None  # admin = all locations
    first_hash = admin.password_hash

    # Second run: no duplicates, password unchanged.
    seed_min(db)
    assert _count(db, Location) == 3
    assert _count(db, User) == 1
    admin2 = db.execute(select(User).where(User.username == "owner")).scalar_one()
    assert admin2.password_hash == first_hash


def test_seed_min_requires_admin_env(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SEED_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    with pytest.raises(SystemExit):
        seed_min(db)
