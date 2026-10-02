"""Property + unit tests for role-based location scoping.

Feature: cinematic-celebration-system, Property 2: Role-based location scoping
is enforced server-side.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.core.errors import LocationAccessDeniedError
from app.core.security import CurrentUser, assert_location_access, get_current_user
from tests.factories import make_location, make_user

pytestmark = pytest.mark.integration


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(assigned=st.integers(1, 5), target=st.integers(1, 5))
def test_staff_location_scoping_property(db: Session, assigned: int, target: int) -> None:
    """Staff may access only their assigned location; cross-location raises 403."""
    actor = CurrentUser(id=1, username="staff", role="staff", location_id=assigned)
    if assigned == target:
        assert_location_access(actor, target)  # no raise
    else:
        with pytest.raises(LocationAccessDeniedError):
            assert_location_access(actor, target)


@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(assigned=st.integers(1, 5), target=st.integers(1, 5))
def test_admin_accesses_any_location_property(
    db: Session, assigned: int, target: int
) -> None:
    """Admins may access any location regardless of assignment."""
    actor = CurrentUser(id=1, username="admin", role="admin", location_id=assigned)
    assert_location_access(actor, target)  # never raises


def test_inactive_user_is_unauthenticated(db: Session) -> None:
    """A deactivated user cannot resolve as the current user."""
    from fastapi import Request

    from app.core.errors import UnauthenticatedError
    from app.core.security import ACCESS_COOKIE_NAME, create_access_token

    loc = make_location(db)
    user = make_user(db, "staff", location_id=loc.id, is_active=False)
    db.commit()
    token = create_access_token(user.id, user.username, "staff", loc.id)

    scope = {
        "type": "http",
        "headers": [],
        "cookies": {ACCESS_COOKIE_NAME: token},
    }
    request = Request(scope)
    request._cookies = {ACCESS_COOKIE_NAME: token}
    with pytest.raises(UnauthenticatedError):
        get_current_user(request, db)
