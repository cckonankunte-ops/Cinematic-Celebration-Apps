"""Preservation tests for the active-slot uniqueness invariant (real PostgreSQL).

Bugfix: booking-uniqueness-per-plan, Property 2: Preservation -
Non-Bug Behavior Unchanged.

These tests encode every NON-``isBugCondition`` behavior that the fix (adding
``plan_id`` to ``uq_bookings_active_slot``) MUST preserve. Per the observation-
first methodology they are written and run against the UNFIXED ``0001`` schema
(the 3-column index on ``(location_id, slot_id, booking_date)`` reflected by
``Base.metadata.create_all`` in ``conftest.py``) and MUST all PASS now. They form
the baseline that task 3.5 re-runs against the fixed ``0002`` schema.

Deliberately, NO ``plan_id``-aware index assertion lives here (that belongs to
task 3.5): every case uses a SINGLE plan so it holds on both the 3-column and the
4-column key. The non-bug behaviors covered:

1. Same-plan duplicate still conflicts (Req 3.1).
2. ``rejected`` / ``expired`` bookings do not hold the slot (Req 3.3).
3. Concurrency - exactly one of two same-key racers wins (Req 3.2).
4. A slot conflict surfaces as ``SlotUnavailableError`` -> 409 (Req 3.4).
5. The explicitly-named partial index ``uq_bookings_active_slot`` exists and is
   partial on ``pending``/``accepted`` (Req 3.5).

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

from __future__ import annotations

import secrets
import threading
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.core.errors import SlotUnavailableError
from app.models.booking import Booking
from app.schemas.booking import BookingCreate
from app.services.booking import create_customer_booking
from tests.factories import make_location, make_plan, make_slot

pytestmark = pytest.mark.integration


def _seed_location_plan_slot(db: Session) -> tuple[int, int, int]:
    """Seed one location, one plan, and one slot owned by that plan.

    Returns ``(location_id, plan_id, slot_id)``. A single plan is used so every
    preservation case keys on the SAME ``(location, plan, slot, date)`` and holds
    identically under the 3-column and 4-column indexes.
    """
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    db.flush()
    return loc.id, plan.id, slot.id


def _make_booking(
    location_id: int,
    plan_id: int,
    slot_id: int,
    booking_date: date,
    status: str,
) -> Booking:
    """Build a minimal valid ``Booking`` row for the given active-slot key."""
    return Booking(
        booking_reference=f"CC-{secrets.token_hex(3)}",
        public_token=secrets.token_urlsafe(12),
        location_id=location_id,
        plan_id=plan_id,
        slot_id=slot_id,
        booking_date=booking_date,
        booking_name="Test",
        email="t@example.com",
        people=4,
        plan_price_paise=400000,
        subtotal_paise=400000,
        total_paise=400000,
        advance_paise=50000,
        status=status,
    )


# ---------------------------------------------------------------------------
# 1. Same-plan duplicate still conflicts (Req 3.1)
# ---------------------------------------------------------------------------
def test_same_plan_duplicate_active_booking_still_conflicts(db: Session) -> None:
    """A second active booking with the SAME key raises on uq_bookings_active_slot.

    Both bookings share the identical ``(location, plan, slot, date)`` and are
    active (``pending`` then ``accepted``). This is a genuine duplicate - NOT the
    bug condition - and must keep raising a unique violation on the preserved,
    explicitly-named index. Preserves Req 3.1.
    """
    # Single plan ⇒ both rows share the identical full 4-column key
    # (location, plan, slot, date), so this still exercises a genuine conflict
    # under the fixed index.
    loc, plan, slot = _seed_location_plan_slot(db)
    booking_date = date.today() + timedelta(days=10)

    db.add(_make_booking(loc, plan, slot, booking_date, "pending"))
    db.commit()

    db.add(_make_booking(loc, plan, slot, booking_date, "accepted"))
    with pytest.raises(IntegrityError) as exc_info:
        db.commit()
    db.rollback()

    # The violation is specifically the active-slot uniqueness index (the name is
    # reused across the fix, which is what keeps the 409 mapping valid).
    assert "uq_bookings_active_slot" in str(exc_info.value.orig)


# ---------------------------------------------------------------------------
# 2. rejected / expired bookings do not hold the slot (Req 3.3)
# ---------------------------------------------------------------------------
def test_rejected_booking_does_not_hold_slot(db: Session) -> None:
    """A ``rejected`` booking lets a later active booking take the same key.

    The partial predicate ``WHERE status IN ('pending', 'accepted')`` excludes
    ``rejected`` rows from the index, so a subsequent active booking for the same
    ``(location, plan, slot, date)`` commits cleanly. Preserves Req 3.3.
    """
    # Single plan ⇒ the rejected and active rows share the full 4-column key
    # (location, plan, slot, date); the partial predicate still excludes the
    # rejected one under the fixed index.
    loc, plan, slot = _seed_location_plan_slot(db)
    booking_date = date.today() + timedelta(days=10)

    db.add(_make_booking(loc, plan, slot, booking_date, "rejected"))
    db.commit()

    # A new active booking for the SAME key is allowed alongside the rejected one.
    db.add(_make_booking(loc, plan, slot, booking_date, "pending"))
    db.commit()


def test_expired_booking_does_not_hold_slot(db: Session) -> None:
    """An ``expired`` booking lets a later active booking take the same key.

    Like ``rejected``, ``expired`` is outside the partial predicate, so it does
    not hold the slot and a later active booking for the same key commits.
    Preserves Req 3.3 (the ``expired`` variant).
    """
    loc, plan, slot = _seed_location_plan_slot(db)
    booking_date = date.today() + timedelta(days=10)

    db.add(_make_booking(loc, plan, slot, booking_date, "expired"))
    db.commit()

    db.add(_make_booking(loc, plan, slot, booking_date, "accepted"))
    db.commit()


# ---------------------------------------------------------------------------
# 3. Concurrency - exactly one of two same-key racers wins (Req 3.2)
# ---------------------------------------------------------------------------
def test_concurrent_same_key_insert_only_one_wins(pg_engine: Engine) -> None:
    """Two threads insert the SAME active key; exactly one commits, one violates.

    Models Req 3.2 at the DB level (mirrors the threading pattern in
    ``test_booking_concurrent.py``): both racers are pinned to the identical
    ``(location, plan, slot, date)`` active booking, so the database serialises
    them and exactly one ``IntegrityError`` on ``uq_bookings_active_slot`` occurs.
    The service-level 409 mapping for this race is covered by
    ``test_concurrent_booking_only_one_wins`` in ``test_booking_concurrent.py``;
    this test asserts the underlying DB guarantee the service relies on.

    Commits run on the shared session engine (bypassing the ``db`` fixture
    truncation), so every table is cleaned afterwards to keep tests isolated.
    """
    maker = sessionmaker(
        bind=pg_engine, autoflush=False, expire_on_commit=False, future=True
    )

    setup = maker()
    try:
        location_id, plan_id, slot_id = _seed_location_plan_slot(setup)
        setup.commit()
    finally:
        setup.close()

    booking_date = date.today() + timedelta(days=14)

    results: dict[str, int] = {"success": 0, "conflict": 0, "other": 0}
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _attempt(index: int) -> None:
        session = maker()
        try:
            # Both racers share the same single plan_id, so they contend on the
            # identical full 4-column key and the race still exercises a real
            # conflict under the fixed index.
            session.add(
                _make_booking(location_id, plan_id, slot_id, booking_date, "pending")
            )
            barrier.wait(timeout=10)
            session.commit()
            with lock:
                results["success"] += 1
        except IntegrityError:
            session.rollback()
            with lock:
                results["conflict"] += 1
        except Exception:  # pragma: no cover - unexpected failure path
            session.rollback()
            with lock:
                results["other"] += 1
        finally:
            session.close()

    threads = [threading.Thread(target=_attempt, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert results["success"] == 1, results
    assert results["conflict"] == 1, results
    assert results["other"] == 0, results

    cleanup = maker()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            cleanup.execute(table.delete())
        cleanup.commit()
    finally:
        cleanup.close()


# ---------------------------------------------------------------------------
# 4. Slot conflict surfaces as SlotUnavailableError -> 409 (Req 3.4)
# ---------------------------------------------------------------------------
def test_slot_conflict_maps_to_slot_unavailable_error(db: Session) -> None:
    """``create_customer_booking`` twice for the SAME key raises SlotUnavailableError.

    The first call creates a ``pending`` booking that holds the slot. The second
    call, for the IDENTICAL valid ``(location, plan, slot, date)``, hits the
    active-slot unique violation which ``_classify_integrity_error`` maps to
    ``SlotUnavailableError`` (-> HTTP 409 "Slot not available"). A single plan is
    used so the service's slot-ownership check passes and the request reaches the
    index. Preserves Req 3.4.

    Uses the function-scoped ``db`` fixture, whose teardown truncates all tables,
    so the committed bookings do not leak into other tests.
    """
    # Single plan ⇒ both requests target the identical full 4-column key, so the
    # second one is a genuine conflict mapped to 409 under the fixed index.
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    db.commit()

    booking_date = date.today() + timedelta(days=14)

    def _request(index: int) -> BookingCreate:
        return BookingCreate(
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=booking_date,
            booking_name=f"Guest {index}",
            email=f"guest{index}@example.com",
            people=4,
        )

    # First booking succeeds and holds the slot.
    create_customer_booking(db, _request(1))

    # Second booking for the SAME key is a genuine conflict -> 409 symptom.
    with pytest.raises(SlotUnavailableError):
        create_customer_booking(db, _request(2))


# ---------------------------------------------------------------------------
# 5. Explicitly-named partial index is preserved (Req 3.5)
# ---------------------------------------------------------------------------
def test_active_slot_index_exists_and_is_partial(db: Session) -> None:
    """``uq_bookings_active_slot`` exists in pg_indexes and is partial.

    Asserts the explicit index name is present and its definition carries the
    ``pending``/``accepted`` partial ``WHERE`` clause, and (under the fixed
    ``0002`` schema reflected by ``conftest.py``) that the key now references
    ``plan_id`` and all four columns ``(location_id, plan_id, slot_id,
    booking_date)``. Mirrors ``test_partial_index_predicate_is_present`` in
    ``test_schema_integrity.py`` and makes the preservation intent explicit here.
    Preserves Req 3.5 and confirms the live 4-column key.
    """
    row = db.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'uq_bookings_active_slot'"
        )
    ).first()
    assert row is not None
    indexdef = row[0]
    # Partial predicate preserved: still restricted to active bookings.
    assert "pending" in indexdef and "accepted" in indexdef
    # Fixed 4-column shape (Req 3.5): plan_id is now part of the key, alongside the
    # other three columns (location_id, slot_id, booking_date).
    assert "plan_id" in indexdef
    for column in ("location_id", "plan_id", "slot_id", "booking_date"):
        assert column in indexdef, f"{column} missing from indexdef: {indexdef}"
