"""Lead follows its booking (lead-crm group 4, real PostgreSQL).

Covers R2.8-R2.11, R8.1-R8.7, R9.3, R9.6, R16.1 and test cases R19.4-R19.8:
- a public booking with a Step 1 token links that lead and sets `booked`;
- without a token a linked `booked` lead is created;
- accept -> won; reject / cancel / expire -> follow_up; review -> booked;
- admin create without a lead creates no lead; from a lead it links (won);
- an invalid lead id is refused before any booking exists;
- a slot 409 links nothing;
- a failing lead hook never changes the booking outcome, and logs no phone.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.core.security import CurrentUser
from app.models.booking import Booking
from app.models.booking_event import BookingEvent
from app.models.lead import Lead, LeadActivity
from app.schemas.booking import AdminBookingCreate
from app.schemas.lead import LeadCreate, WebsiteLeadIn
from app.services import booking as booking_service
from app.services import leads as leads_service
from tests.factories import future_date, make_location, make_plan, make_slot, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}
PHONE = "9876543210"
OTHER_PHONE = "9123456780"
THIRD_PHONE = "9988776655"


def _seed(db: Session) -> tuple[int, int, int, int, int]:
    loc = make_location(db)
    plan = make_plan(db, loc.id, max_people_allowed=10)
    slot = make_slot(db, plan.id)
    slot2 = make_slot(db, plan.id, description="3 PM - 5 PM",
                      start_time=datetime(2000, 1, 1, 15, 0).time(), sort_order=2)
    admin = make_user(db, "admin")
    db.commit()
    return loc.id, plan.id, slot.id, slot2.id, admin.id


def _admin(db: Session, admin_id: int) -> CurrentUser:
    return CurrentUser(id=admin_id, username="admin", role="admin", location_id=None)


def _payload(loc_id: int, plan_id: int, slot_id: int, phone: str = PHONE, **extra) -> dict:
    return {
        "location_id": loc_id,
        "plan_id": plan_id,
        "slot_id": slot_id,
        "booking_date": future_date().isoformat(),
        "booking_name": "Priya S",
        "phone": phone,
        "people": 3,
        "kids": 1,
        "special_decor": [],
        "combos": [],
        **extra,
    }


@pytest.fixture
def book(client: TestClient, db: Session) -> Callable[[dict], Booking]:
    """POST a public booking request and return the created Booking row."""

    def _book(payload: dict) -> Booking:
        resp = client.post("/api/v1/public/bookings", json=payload, headers=_ORIGIN)
        assert resp.status_code == 201, resp.text
        return db.execute(
            select(Booking).where(Booking.public_token == resp.json()["booking_token"])
        ).scalar_one()

    return _book


def _lead_for(db: Session, booking_id: int) -> Lead:
    db.expire_all()
    return db.execute(select(Lead).where(Lead.booking_id == booking_id)).scalar_one()


def _lead_count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(Lead)).scalar_one()


# --- public bookings -------------------------------------------------------------


def test_booking_with_token_links_the_step1_lead(db: Session, book) -> None:
    loc_id, plan_id, slot_id, _, _ = _seed(db)
    token = leads_service.capture_website_lead(
        db,
        WebsiteLeadIn(location_id=loc_id, phone=PHONE, attribution={"fbclid": "IwAR"}),
    )
    step1 = db.execute(select(Lead)).scalar_one()

    booking = book(_payload(loc_id, plan_id, slot_id, lead_token=token))

    lead = _lead_for(db, booking.id)
    assert lead.id == step1.id
    assert (lead.status, lead.channel) == ("booked", "meta_ads")
    assert lead.guests == 4 and lead.preferred_date == booking.booking_date
    types = [
        a.type
        for a in db.execute(
            select(LeadActivity).where(LeadActivity.lead_id == lead.id)
        ).scalars()
    ]
    assert "booking_linked" in types
    assert _lead_count(db) == 1


def test_booking_without_token_creates_booked_lead(db: Session, book) -> None:
    loc_id, plan_id, slot_id, _, _ = _seed(db)
    booking = book(_payload(loc_id, plan_id, slot_id, phone="+91 98765 43210"))
    lead = _lead_for(db, booking.id)
    assert (lead.source, lead.status, lead.phone) == ("website", "booked", PHONE)


def test_slot_conflict_links_nothing(db: Session, book, client: TestClient) -> None:
    loc_id, plan_id, slot_id, _, _ = _seed(db)
    book(_payload(loc_id, plan_id, slot_id))
    token = leads_service.capture_website_lead(
        db, WebsiteLeadIn(location_id=loc_id, phone=OTHER_PHONE)
    )
    resp = client.post(
        "/api/v1/public/bookings",
        json=_payload(loc_id, plan_id, slot_id, phone=OTHER_PHONE, lead_token=token),
        headers=_ORIGIN,
    )
    assert resp.status_code == 409
    db.expire_all()
    other = db.execute(select(Lead).where(Lead.phone == OTHER_PHONE)).scalar_one()
    assert (other.status, other.booking_id) == ("new", None)


# --- status follow-through ---------------------------------------------------------


def test_accept_sets_won(db: Session, book) -> None:
    loc_id, plan_id, slot_id, _, admin_id = _seed(db)
    booking = book(_payload(loc_id, plan_id, slot_id))
    booking_service.accept_booking(
        db, booking.id, override_advance=True, actor=_admin(db, admin_id)
    )
    assert _lead_for(db, booking.id).status == "won"


@pytest.mark.parametrize("action", ["reject", "cancel"])
def test_reject_or_cancel_sets_follow_up(db: Session, book, action: str) -> None:
    loc_id, plan_id, slot_id, _, admin_id = _seed(db)
    actor = _admin(db, admin_id)
    booking = book(_payload(loc_id, plan_id, slot_id))
    if action == "reject":
        booking_service.reject_booking(db, booking.id, actor=actor)
    else:
        booking_service.cancel_booking(db, booking.id, reason=None, actor=actor)
    lead = _lead_for(db, booking.id)
    assert lead.status == "follow_up"
    assert lead.follow_up_at is not None


def test_cancel_after_won_sets_follow_up(db: Session, book) -> None:
    loc_id, plan_id, slot_id, _, admin_id = _seed(db)
    actor = _admin(db, admin_id)
    booking = book(_payload(loc_id, plan_id, slot_id))
    booking_service.accept_booking(db, booking.id, override_advance=True, actor=actor)
    booking_service.cancel_booking(db, booking.id, reason="plans changed", actor=actor)
    assert _lead_for(db, booking.id).status == "follow_up"


def test_expire_then_review(db: Session, book) -> None:
    loc_id, plan_id, slot_id, _, admin_id = _seed(db)
    booking = book(_payload(loc_id, plan_id, slot_id))
    db.get(Booking, booking.id).created_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()

    assert booking_service.expire_pending_bookings(db) == 1
    assert _lead_for(db, booking.id).status == "follow_up"

    booking_service.review_booking(db, booking.id, actor=_admin(db, admin_id))
    assert _lead_for(db, booking.id).status == "booked"


def test_rejected_booking_with_other_open_enquiry_closes_old_lead(db: Session, book) -> None:
    loc_id, plan_id, slot_id, _, admin_id = _seed(db)
    booking = book(_payload(loc_id, plan_id, slot_id))
    newer = leads_service.capture_website_lead(
        db, WebsiteLeadIn(location_id=loc_id, phone=PHONE)
    )
    assert newer
    booking_service.reject_booking(db, booking.id, actor=_admin(db, admin_id))
    old = _lead_for(db, booking.id)
    assert (old.status, old.close_reason) == ("lost", "other")
    assert db.execute(
        select(func.count()).select_from(Lead).where(Lead.status == "new")
    ).scalar_one() == 1


# --- admin bookings ----------------------------------------------------------------


def _admin_create(loc_id: int, plan_id: int, slot_id: int, **extra) -> AdminBookingCreate:
    return AdminBookingCreate(
        location_id=loc_id,
        plan_id=plan_id,
        slot_id=slot_id,
        booking_date=future_date(),
        booking_name="Walk in",
        phone=PHONE,
        people=2,
        **extra,
    )


def test_admin_booking_without_lead_creates_no_lead(db: Session) -> None:
    loc_id, plan_id, slot_id, _, admin_id = _seed(db)
    booking_service.create_admin_booking(
        db, _admin_create(loc_id, plan_id, slot_id), _admin(db, admin_id)
    )
    assert _lead_count(db) == 0


def test_convert_lead_to_admin_booking(db: Session) -> None:
    loc_id, plan_id, slot_id, _, admin_id = _seed(db)
    actor = _admin(db, admin_id)
    lead = leads_service.create_manual_lead(
        db, LeadCreate(location_id=loc_id, phone=PHONE, source="whatsapp"), actor
    ).lead
    booking = booking_service.create_admin_booking(
        db, _admin_create(loc_id, plan_id, slot_id, lead_id=lead.id), actor
    )
    linked = _lead_for(db, booking.id)
    assert linked.id == lead.id
    assert linked.status == "won"  # admin bookings are created accepted


def test_invalid_lead_id_is_refused_before_booking(db: Session) -> None:
    loc_id, plan_id, slot_id, _, admin_id = _seed(db)
    actor = _admin(db, admin_id)
    other = make_location(db, name="Ecity")
    db.commit()
    lost = leads_service.create_manual_lead(
        db, LeadCreate(location_id=loc_id, phone=OTHER_PHONE), actor
    ).lead
    db.get(Lead, lost.id).status = "lost"
    db.get(Lead, lost.id).close_reason = "no_response"
    db.commit()
    foreign = leads_service.create_manual_lead(
        db, LeadCreate(location_id=other.id, phone=PHONE), actor
    ).lead

    for bad in (999_999, lost.id, foreign.id):
        with pytest.raises(ValidationFailedError):
            booking_service.create_admin_booking(
                db, _admin_create(loc_id, plan_id, slot_id, lead_id=bad), actor
            )
        db.rollback()
    assert db.execute(select(func.count()).select_from(Booking)).scalar_one() == 0


# --- failure isolation --------------------------------------------------------------


class _LogRecorder:
    """Stands in for the module's structlog logger (cached loggers bypass capsys)."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []

    def error(self, event: str, **kw: object) -> None:
        self.records.append((event, kw))

    info = warning = error


def test_lead_hook_failure_never_breaks_bookings(
    db: Session, book, monkeypatch: pytest.MonkeyPatch
) -> None:
    loc_id, plan_id, slot_id, slot2_id, admin_id = _seed(db)
    actor = _admin(db, admin_id)
    recorder = _LogRecorder()

    def boom(*_args, **_kwargs):
        raise RuntimeError("lead store down")

    monkeypatch.setattr(leads_service, "log", recorder)
    monkeypatch.setattr(leads_service, "_apply_public_link", boom)
    monkeypatch.setattr(leads_service, "_apply_status_change", boom)

    first = book(_payload(loc_id, plan_id, slot_id))
    second = book(_payload(loc_id, plan_id, slot2_id, phone=OTHER_PHONE))
    assert _lead_count(db) == 0

    accepted = booking_service.accept_booking(db, first.id, override_advance=True, actor=actor)
    assert accepted.status == "accepted"
    rejected = booking_service.reject_booking(db, second.id, actor=actor)
    assert rejected.status == "rejected"
    cancelled = booking_service.cancel_booking(db, first.id, reason=None, actor=actor)
    assert cancelled.status == "cancelled"

    events = db.execute(
        select(BookingEvent.event_type).where(BookingEvent.booking_id == first.id)
    ).scalars().all()
    assert list(events).count("accepted") == 1 and "cancelled" in events

    # Expiry and review still work (slot 2 is free again after the rejection).
    third = book(_payload(loc_id, plan_id, slot2_id, phone=THIRD_PHONE))
    db.get(Booking, third.id).created_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    assert booking_service.expire_pending_bookings(db) == 1
    db.expire_all()
    assert db.get(Booking, third.id).status == "expired"
    reviewed = booking_service.review_booking(db, third.id, actor=actor)
    assert reviewed.status == "pending"
    assert _lead_count(db) == 0

    failures = [kw for event, kw in recorder.records if event == "lead_hook_failed"]
    # 3 links + accept + reject + cancel + expire + review, code and booking id only.
    assert len(failures) == 8
    assert all(set(kw) == {"code", "booking_id"} for kw in failures)
    logged = repr(recorder.records)
    assert all(p not in logged for p in (PHONE, OTHER_PHONE, THIRD_PHONE))
