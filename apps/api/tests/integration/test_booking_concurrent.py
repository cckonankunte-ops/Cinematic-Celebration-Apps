"""Concurrent double-booking integration test.

Feature: cinematic-celebration-system, Property 5: Double-booking is prevented
for all concurrent requests. Two threads attempt to create a customer booking
for the same (location, slot, date); exactly one succeeds and the other raises
SlotUnavailableError.

Validates: Requirements 5.6
"""

from __future__ import annotations

import threading
from datetime import date, timedelta

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.core.errors import SlotUnavailableError
from app.schemas.booking import BookingCreate
from app.services.booking import create_customer_booking
from tests.factories import make_location, make_plan, make_slot

pytestmark = pytest.mark.integration


def _seed_slot(session: Session) -> tuple[int, int, int]:
    loc = make_location(session)
    plan = make_plan(session, loc.id, max_people_allowed=10)
    slot = make_slot(session, plan.id)
    session.commit()
    return loc.id, plan.id, slot.id


def test_concurrent_booking_only_one_wins(pg_engine: Engine) -> None:
    """Two threads book the same slot/date: exactly one succeeds, one 409."""
    maker = sessionmaker(
        bind=pg_engine, autoflush=False, expire_on_commit=False, future=True
    )

    setup = maker()
    try:
        location_id, plan_id, slot_id = _seed_slot(setup)
    finally:
        setup.close()

    booking_date = date.today() + timedelta(days=14)

    results: dict[str, int] = {"success": 0, "conflict": 0, "other": 0}
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _attempt(index: int) -> None:
        session = maker()
        try:
            barrier.wait(timeout=10)
            create_customer_booking(
                session,
                BookingCreate(
                    location_id=location_id,
                    plan_id=plan_id,
                    slot_id=slot_id,
                    booking_date=booking_date,
                    booking_name=f"Racer {index}",
                    email=f"racer{index}@example.com",
                    people=4,
                ),
            )
            with lock:
                results["success"] += 1
        except SlotUnavailableError:
            with lock:
                results["conflict"] += 1
        except Exception:  # pragma: no cover - unexpected failure path
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

    # This test commits directly on the shared session engine (bypassing the
    # function-scoped `db` fixture truncation), so clean every table afterwards
    # to keep other tests isolated.
    cleanup = maker()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            cleanup.execute(table.delete())
        cleanup.commit()
    finally:
        cleanup.close()
