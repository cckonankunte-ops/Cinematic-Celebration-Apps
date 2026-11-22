"""Receptionist role (staff + lead CRM) and staff without leads (real PostgreSQL).

- Staff: every /admin/leads endpoint is 403, and a booking sent with lead_id is
  refused before any booking is created.
- Receptionist: the lead CRM for their branch, plus everything staff can do
  (bookings, time sheet), under the staff booking-time rules; still not the
  admin-only areas or the lead dashboard.
- Only admins and the branch's receptionists can be assigned a lead.
- An admin can create a receptionist, who logs in with that role.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, ValidationFailedError
from app.core.security import CurrentUser
from app.models.booking import Booking
from app.models.lead import Lead
from app.schemas.booking import AdminBookingCreate
from app.schemas.lead import LeadCreate, LeadUpdate
from app.services import booking as booking_service
from app.services import leads as leads_service
from app.services.slots import ActorKind, actor_kind_from_role
from tests.factories import future_date, make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login(client: TestClient, username: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200, resp.text


def _actor(user, role: str) -> CurrentUser:
    return CurrentUser(id=user.id, username=user.username, role=role, location_id=user.location_id)


def _lead(db: Session, location_id: int, phone: str = "9876543210") -> Lead:
    lead = Lead(location_id=location_id, phone=phone, source="whatsapp", channel="manual")
    db.add(lead)
    db.flush()
    return lead


# --- staff: no leads -----------------------------------------------------------------


def test_staff_get_403_on_every_lead_endpoint(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    staff = make_user(db, "staff", location_id=loc.id)
    lead = _lead(db, loc.id)
    db.commit()
    _login(client, staff.username)

    gets = [
        f"/api/v1/admin/leads?location_id={loc.id}",
        f"/api/v1/admin/leads/counts?location_id={loc.id}",
        f"/api/v1/admin/leads/follow-ups?location_id={loc.id}",
        f"/api/v1/admin/leads/assignable-users?location_id={loc.id}",
        "/api/v1/admin/leads/dashboard",
        f"/api/v1/admin/leads/{lead.id}",
    ]
    for path in gets:
        assert client.get(path, headers=_ORIGIN).status_code == 403, path

    writes = [
        ("post", "/api/v1/admin/leads", {"location_id": loc.id, "phone": "9123456780"}),
        ("patch", f"/api/v1/admin/leads/{lead.id}", {"name": "X"}),
        ("post", f"/api/v1/admin/leads/{lead.id}/activities", {"type": "note", "text": "hi"}),
        ("post", f"/api/v1/admin/leads/{lead.id}/enquiry-code", {"code": "ABC234"}),
    ]
    for method, path, body in writes:
        resp = getattr(client, method)(path, json=body, headers=_ORIGIN)
        assert resp.status_code == 403, path

    db.expire_all()
    assert db.execute(select(func.count()).select_from(Lead)).scalar_one() == 1
    assert db.get(Lead, lead.id).name is None


def test_staff_cannot_book_from_a_lead(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    staff = make_user(db, "staff", location_id=loc.id)
    lead = _lead(db, loc.id)
    db.commit()

    body = AdminBookingCreate(
        location_id=loc.id,
        plan_id=plan.id,
        slot_id=slot.id,
        booking_date=future_date(),
        booking_name="Walk in",
        phone="9876543210",
        people=2,
        lead_id=lead.id,
    )
    with pytest.raises(ForbiddenError):
        booking_service.create_admin_booking(db, body, _actor(staff, "staff"))
    db.rollback()
    assert db.execute(select(func.count()).select_from(Booking)).scalar_one() == 0


def test_staff_can_still_book_without_a_lead(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    slot = make_slot(db, plan.id)
    staff = make_user(db, "staff", location_id=loc.id)
    db.commit()
    booking = booking_service.create_admin_booking(
        db,
        AdminBookingCreate(
            location_id=loc.id,
            plan_id=plan.id,
            slot_id=slot.id,
            booking_date=future_date(),
            booking_name="Walk in",
            phone="9876543210",
            people=2,
        ),
        _actor(staff, "staff"),
    )
    assert booking.id is not None


# --- receptionist: staff + leads ------------------------------------------------------


def test_receptionist_uses_leads_and_staff_pages_but_not_admin_areas(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    rec = make_user(db, "receptionist", location_id=loc.id)
    db.commit()
    _login(client, rec.username)

    me = client.get("/api/v1/auth/me", headers=_ORIGIN).json()
    assert (me["role"], me["location_id"]) == ("receptionist", loc.id)

    created = client.post(
        "/api/v1/admin/leads",
        json={"location_id": loc.id, "phone": "9876543210"},
        headers=_ORIGIN,
    )
    assert created.status_code == 201, created.text
    leads = client.get(f"/api/v1/admin/leads?location_id={loc.id}", headers=_ORIGIN)
    assert leads.status_code == 200

    # Everything staff can do.
    bookings = client.get(f"/api/v1/admin/bookings?location_id={loc.id}", headers=_ORIGIN)
    assert bookings.status_code == 200, bookings.text
    timesheet = client.get(
        f"/api/v1/admin/timesheet?location_id={loc.id}&date={future_date().isoformat()}",
        headers=_ORIGIN,
    )
    assert timesheet.status_code == 200, timesheet.text

    # Still not admin-only areas.
    assert client.get("/api/v1/admin/leads/dashboard", headers=_ORIGIN).status_code == 403
    assert client.get("/api/v1/admin/users", headers=_ORIGIN).status_code == 403
    assert client.get("/api/v1/admin/locations", headers=_ORIGIN).status_code == 403


def test_receptionist_is_limited_to_own_branch(client: TestClient, db: Session) -> None:
    own = make_location(db, name="Hulimavu")
    other = make_location(db, name="Ecity")
    rec = make_user(db, "receptionist", location_id=own.id)
    theirs = _lead(db, other.id)
    db.commit()
    _login(client, rec.username)
    assert client.get(f"/api/v1/admin/leads/{theirs.id}", headers=_ORIGIN).status_code == 403
    assert (
        client.get(f"/api/v1/admin/bookings?location_id={other.id}", headers=_ORIGIN).status_code
        == 403
    )


def test_receptionist_books_under_staff_time_rules() -> None:
    assert actor_kind_from_role("receptionist") == ActorKind.STAFF
    assert actor_kind_from_role("staff") == ActorKind.STAFF
    assert actor_kind_from_role("admin") == ActorKind.ADMIN
    assert actor_kind_from_role(None) == ActorKind.PUBLIC


# --- assignment -------------------------------------------------------------------------


def test_only_admins_and_branch_receptionists_can_be_assigned(db: Session) -> None:
    own = make_location(db, name="Hulimavu")
    other = make_location(db, name="Ecity")
    admin = make_user(db, "admin")
    rec = make_user(db, "receptionist", location_id=own.id)
    rec_other = make_user(db, "receptionist", location_id=other.id)
    staff = make_user(db, "staff", location_id=own.id)
    db.commit()
    actor = _actor(admin, "admin")
    lead = leads_service.create_manual_lead(
        db, LeadCreate(location_id=own.id, phone="9876543210"), actor
    ).lead

    users = leads_service.assignable_users(db, actor, own.id)
    assert {u.id for u in users} == {admin.id, rec.id}

    for user_id in (staff.id, rec_other.id):
        with pytest.raises(ValidationFailedError):
            leads_service.update_lead(db, lead.id, LeadUpdate(assigned_user_id=user_id), actor)
        db.rollback()
    updated = leads_service.update_lead(db, lead.id, LeadUpdate(assigned_user_id=rec.id), actor)
    assert updated.assigned_user_id == rec.id


# --- creating receptionists ----------------------------------------------------------------


def test_admin_creates_a_receptionist_who_can_log_in(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin")
    db.commit()
    _login(client, admin.username)

    resp = client.post(
        "/api/v1/admin/users",
        json={
            "username": "front-desk",
            "password": "pw-123456",
            "role": "receptionist",
            "location_id": loc.id,
        },
        headers=_ORIGIN,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "receptionist"

    client.post("/api/v1/auth/logout", headers=_ORIGIN)
    _login(client, "front-desk")
    assert client.get("/api/v1/auth/me", headers=_ORIGIN).json()["role"] == "receptionist"
