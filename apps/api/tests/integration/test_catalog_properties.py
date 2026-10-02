"""Property tests for catalog filtering.

Feature: cinematic-celebration-system, Property 1: Active locations are always
filtered in public responses.
Feature: cinematic-celebration-system, Property 3: Catalog items outside their
validity window or inactive are excluded.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.location import Location
from app.services import catalog
from tests.factories import make_cake, make_location

pytestmark = pytest.mark.integration


def _clear_locations(db: Session) -> None:
    for loc in db.execute(select(Location)).scalars().all():
        db.delete(loc)
    db.flush()


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(active=st.integers(0, 6), inactive=st.integers(0, 6))
def test_only_active_locations_returned(db: Session, active: int, inactive: int) -> None:
    """Property 1: public locations endpoint returns only active locations."""
    _clear_locations(db)
    for i in range(active):
        make_location(db, name=f"Active{i}", is_active=True)
    for i in range(inactive):
        make_location(db, name=f"Inactive{i}", is_active=False)
    db.flush()

    result = catalog.list_active_locations(db)
    assert len(result) == active
    # None of the returned slugs belong to an inactive location (all start "active").
    assert all(r.name.startswith("Active") for r in result)


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    offset_from=st.integers(-30, 30),
    window=st.integers(0, 20),
    is_active=st.booleans(),
    query_offset=st.integers(-40, 40),
)
def test_catalog_validity_window_and_active(
    db: Session, offset_from: int, window: int, is_active: bool, query_offset: int
) -> None:
    """Property 3: a cake is returned iff active AND query date in [from, to]."""
    _clear_locations(db)
    loc = make_location(db)
    today = date.today()
    eff_from = today + timedelta(days=offset_from)
    eff_to = eff_from + timedelta(days=window)
    cake = make_cake(db, loc.id, is_active=is_active)
    cake.effective_from = eff_from
    cake.effective_to = eff_to
    db.flush()

    query_date = today + timedelta(days=query_offset)
    result = catalog.list_cakes(db, loc.id, query_date)

    in_window = eff_from <= query_date <= eff_to
    expected_present = is_active and in_window
    assert (len(result) == 1) is expected_present
