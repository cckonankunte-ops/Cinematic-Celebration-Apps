"""Lead service rules (lead-crm group 3, real PostgreSQL).

Covers: website capture + token (R2.2, R2.3, R2.7, R17.10), duplicates incl.
concurrent creates (R6.1, R6.2, R6.4), close rules (R1.8, R1.9, R7.7), contact
activities (R7.3, R7.4), follow-ups (R7.6), assignment (R12.4), branch access
(R12.3), enquiry forms + honeypot (R3.2, R3.7), enquiry codes (R18.5, R18.8-R18.10),
malformed attribution (R17.8).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import LocationAccessDeniedError, ValidationFailedError
from app.core.security import CurrentUser
from app.models.lead import EnquiryCode, Lead, LeadActivity
from app.schemas.lead import (
    ActivityCreate,
    EnquiryCodeIn,
    EnquiryIn,
    LeadCreate,
    LeadUpdate,
    WebsiteLeadIn,
)
from app.services import leads as svc
from tests.factories import make_location, make_plan, make_user

pytestmark = pytest.mark.integration

PHONE = "9876543210"


def _actor(user) -> CurrentUser:
    role = "admin" if user.location_id is None else "staff"
    return CurrentUser(id=user.id, username=user.username, role=role, location_id=user.location_id)


def _count(db: Session, *where) -> int:
    return db.execute(select(func.count()).select_from(Lead).where(*where)).scalar_one()


def _activities(db: Session, lead_id: int) -> list[LeadActivity]:
    return list(
        db.execute(
            select(LeadActivity).where(LeadActivity.lead_id == lead_id).order_by(LeadActivity.id)
        ).scalars()
    )


# --- website capture ----------------------------------------------------------


def test_step1_capture_creates_lead_and_token_updates_same_lead(db: Session) -> None:
    loc = make_location(db)
    plan = make_plan(db, loc.id)
    db.commit()

    token = svc.capture_website_lead(
        db,
        WebsiteLeadIn(
            location_id=loc.id,
            phone="+91 98765 43210",
            name="Asha",
            plan_id=plan.id,
            guests=2,
            attribution={"fbclid": "IwAR1", "landing_path": "/?utm_source=ig"},
        ),
    )
    assert token
    lead = db.execute(select(Lead)).scalar_one()
    assert (lead.source, lead.status, lead.channel, lead.phone) == (
        "website", "new", "meta_ads", PHONE,
    )
    assert lead.plan_id == plan.id and lead.guests == 2
    assert lead.landing_path == "/"
    assert lead.lead_token_hash == svc.hash_token(token)

    again = svc.capture_website_lead(
        db,
        WebsiteLeadIn(
            lead_token=token,
            location_id=loc.id,
            phone=PHONE,
            guests=4,
            attribution={"utm_source": "google", "utm_medium": "cpc"},
        ),
    )
    assert again == token
    assert _count(db) == 1
    db.refresh(lead)
    assert lead.guests == 4
    assert lead.channel == "meta_ads"  # attribution from creation is kept (R17.10)


def test_token_with_different_phone_corrects_the_same_lead(db: Session) -> None:
    """A changed phone on Step 1 is a typo fix: same lead, same token, new number."""
    loc = make_location(db)
    db.commit()
    token = svc.capture_website_lead(db, WebsiteLeadIn(location_id=loc.id, phone=PHONE))
    again = svc.capture_website_lead(
        db, WebsiteLeadIn(lead_token=token, location_id=loc.id, phone="9123456780")
    )
    assert again == token
    assert _count(db) == 1
    lead = db.execute(select(Lead)).scalar_one()
    assert (lead.phone, lead.status) == ("9123456780", "new")
    assert svc.PHONE_CORRECTED_TEXT in [a.text for a in _activities(db, lead.id)]


def test_token_from_another_branch_starts_a_new_lead(db: Session) -> None:
    loc = make_location(db)
    other_branch = make_location(db, name="Ecity")
    db.commit()
    token = svc.capture_website_lead(db, WebsiteLeadIn(location_id=loc.id, phone=PHONE))
    other = svc.capture_website_lead(
        db, WebsiteLeadIn(lead_token=token, location_id=other_branch.id, phone=PHONE)
    )
    assert other != token
    assert _count(db) == 2


def test_unknown_or_old_token_uses_duplicate_rule(db: Session) -> None:
    loc = make_location(db)
    db.commit()
    token = svc.capture_website_lead(db, WebsiteLeadIn(location_id=loc.id, phone=PHONE))
    later = datetime.now(UTC) + timedelta(days=8)
    new_token = svc.capture_website_lead(
        db, WebsiteLeadIn(lead_token=token, location_id=loc.id, phone=PHONE), now=later
    )
    assert new_token != token
    assert _count(db) == 1  # attached to the same open lead, not duplicated


def test_unknown_branch_is_rejected(db: Session) -> None:
    with pytest.raises(ValidationFailedError):
        svc.capture_website_lead(db, WebsiteLeadIn(location_id=999_999, phone=PHONE))


def test_invalid_phone_and_ignored_client_fields() -> None:
    with pytest.raises(ValidationError):
        WebsiteLeadIn(location_id=1, phone="12345")
    data = WebsiteLeadIn.model_validate(
        {"location_id": 1, "phone": PHONE, "status": "won", "note": "x", "assigned_user_id": 3}
    )
    assert not hasattr(data, "status") and not hasattr(data, "note")


def test_malformed_attribution_is_dropped() -> None:
    data = WebsiteLeadIn(location_id=1, phone=PHONE, attribution={"utm_source": "x" * 500})
    assert data.attribution is None
    data = WebsiteLeadIn(location_id=1, phone=PHONE, attribution="not-an-object")
    assert data.attribution is None


# --- duplicates ----------------------------------------------------------------


def test_repeat_enquiry_attaches_and_fills_only_gaps(db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin")
    db.commit()
    result = svc.create_manual_lead(
        db, LeadCreate(location_id=loc.id, phone=PHONE, name="Ravi"), _actor(admin)
    )
    assert result.created
    svc.create_enquiry_lead(
        db,
        EnquiryIn(source="homepage_form", location_id=loc.id, phone=PHONE, name="Someone",
                  message="Need a slot on Sunday", email="r@example.com"),
    )
    assert _count(db) == 1
    lead = db.get(Lead, result.lead.id)
    db.refresh(lead)
    assert lead.name == "Ravi"  # existing value kept
    assert lead.message == "Need a slot on Sunday"  # empty field filled
    texts = [a.text or "" for a in _activities(db, lead.id)]
    assert any(t.startswith("Repeat enquiry via homepage enquiry form") for t in texts)
    assert any("Email: r@example.com" in t for t in texts)


def test_closed_lead_means_new_lead(db: Session) -> None:
    loc = make_location(db)
    db.add(Lead(location_id=loc.id, phone=PHONE, source="phone", status="lost",
                close_reason="no_response"))
    db.commit()
    svc.capture_website_lead(db, WebsiteLeadIn(location_id=loc.id, phone=PHONE))
    assert _count(db) == 2


def test_enquiry_attaches_to_booked_lead_but_step1_does_not(db: Session) -> None:
    loc = make_location(db)
    db.add(Lead(location_id=loc.id, phone=PHONE, source="website", status="booked"))
    db.commit()
    svc.create_enquiry_lead(
        db, EnquiryIn(source="contact_form", location_id=loc.id, phone=PHONE, name="A")
    )
    assert _count(db) == 1
    svc.capture_website_lead(db, WebsiteLeadIn(location_id=loc.id, phone=PHONE))
    assert _count(db) == 2  # a new booking attempt gets its own pre-booking lead


def test_same_phone_other_branch_is_separate(db: Session) -> None:
    a = make_location(db)
    b = make_location(db, name="Ecity")
    db.commit()
    svc.capture_website_lead(db, WebsiteLeadIn(location_id=a.id, phone=PHONE))
    svc.capture_website_lead(db, WebsiteLeadIn(location_id=b.id, phone=PHONE))
    assert _count(db) == 2


def test_concurrent_creates_yield_one_open_lead(db: Session, pg_engine: Engine) -> None:
    loc = make_location(db)
    db.commit()
    maker = sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        session = maker()
        try:
            barrier.wait(timeout=10)
            svc.capture_website_lead(session, WebsiteLeadIn(location_id=loc.id, phone=PHONE))
        except BaseException as exc:  # noqa: BLE001 - surfaced below
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors
    db.expire_all()
    assert _count(db, Lead.phone == PHONE) == 1


# --- status, activities, follow-ups ---------------------------------------------


def test_close_rules_and_manual_booked_won_rejected(db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin")
    db.commit()
    actor = _actor(admin)
    follow = datetime.now(UTC) + timedelta(days=1)
    lead_id = svc.create_manual_lead(
        db, LeadCreate(location_id=loc.id, phone=PHONE, follow_up_at=follow), actor
    ).lead.id

    with pytest.raises(ValidationFailedError):
        svc.update_lead(db, lead_id, LeadUpdate(status="lost"), actor)
    db.rollback()
    for status in ("booked", "won"):
        with pytest.raises(ValidationFailedError):
            svc.update_lead(db, lead_id, LeadUpdate(status=status), actor)
        db.rollback()

    lead = svc.update_lead(
        db, lead_id, LeadUpdate(status="lost", close_reason="price_budget"), actor
    )
    assert (lead.status, lead.close_reason, lead.follow_up_at) == ("lost", "price_budget", None)

    with pytest.raises(ValidationFailedError):
        svc.update_lead(db, lead_id, LeadUpdate(follow_up_at=follow), actor)
    db.rollback()

    reopened = svc.update_lead(db, lead_id, LeadUpdate(status="contacted"), actor)
    assert reopened.close_reason is None


def test_call_marks_contacted_and_first_contacted(db: Session) -> None:
    loc = make_location(db)
    staff = make_user(db, "staff", location_id=loc.id)
    db.commit()
    actor = _actor(staff)
    lead_id = svc.create_manual_lead(db, LeadCreate(location_id=loc.id, phone=PHONE), actor).lead.id

    lead = svc.add_activity(db, lead_id, ActivityCreate(type="note", text="hi"), actor)
    assert lead.status == "new" and lead.first_contacted_at is None

    lead = svc.add_activity(db, lead_id, ActivityCreate(type="call"), actor)
    assert lead.status == "contacted"
    assert lead.first_contacted_at is not None
    types = [a.type for a in _activities(db, lead_id)]
    assert types[-2:] == ["status_change", "call"]
    assert lead.last_activity_at == max(a.created_at for a in _activities(db, lead_id))


def test_follow_up_moves_new_to_follow_up(db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin")
    db.commit()
    actor = _actor(admin)
    when = datetime.now(UTC) + timedelta(hours=3)
    lead = svc.create_manual_lead(
        db, LeadCreate(location_id=loc.id, phone=PHONE, note="asked price", follow_up_at=when),
        actor,
    ).lead
    assert lead.status == "follow_up"
    types = [a.type for a in _activities(db, lead.id)]
    assert "note" in types and "follow_up_set" in types


def test_assignment_and_branch_access(db: Session) -> None:
    a = make_location(db)
    b = make_location(db, name="Ecity")
    staff_a = make_user(db, "staff", location_id=a.id)
    staff_b = make_user(db, "staff", location_id=b.id)
    admin = make_user(db, "admin")
    inactive = make_user(db, "staff", location_id=a.id, is_active=False)
    db.commit()
    lead_id = svc.create_manual_lead(
        db, LeadCreate(location_id=a.id, phone=PHONE), _actor(staff_a)
    ).lead.id

    for bad in (staff_b.id, inactive.id):
        with pytest.raises(ValidationFailedError):
            svc.update_lead(db, lead_id, LeadUpdate(assigned_user_id=bad), _actor(admin))
        db.rollback()
    assert svc.update_lead(
        db, lead_id, LeadUpdate(assigned_user_id=staff_a.id), _actor(admin)
    ).assigned_user_id == staff_a.id
    assert svc.update_lead(
        db, lead_id, LeadUpdate(assigned_user_id=admin.id), _actor(staff_a)
    ).assigned_user_id == admin.id

    with pytest.raises(LocationAccessDeniedError):
        svc.get_lead(db, lead_id, _actor(staff_b))
    with pytest.raises(LocationAccessDeniedError):
        svc.create_manual_lead(db, LeadCreate(location_id=a.id, phone="9123456780"),
                               _actor(staff_b))


# --- enquiry forms and codes ----------------------------------------------------


def test_honeypot_stores_nothing(db: Session) -> None:
    loc = make_location(db)
    db.commit()
    svc.create_enquiry_lead(
        db,
        EnquiryIn(source="homepage_form", location_id=loc.id, phone=PHONE, name="Bot",
                  website="http://spam"),
    )
    assert _count(db) == 0


def test_enquiry_code_register_and_link(db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin")
    db.commit()
    actor = _actor(admin)

    svc.register_enquiry_code(
        db,
        EnquiryCodeIn(code="w4k7xq", location_id=None,
                      attribution={"utm_source": "instagram", "utm_medium": "paid",
                                   "utm_campaign": "diwali"}),
    )
    # Re-registration keeps the original attribution and updates the branch.
    svc.register_enquiry_code(
        db, EnquiryCodeIn(code="W4K7XQ", location_id=loc.id, attribution={"gclid": "x"})
    )
    code = db.execute(select(EnquiryCode)).scalar_one()
    assert (code.code, code.channel, code.utm_campaign, code.location_id) == (
        "W4K7XQ", "meta_ads", "diwali", loc.id,
    )

    first = svc.create_manual_lead(
        db, LeadCreate(location_id=loc.id, phone=PHONE, source="whatsapp", enquiry_code="w4k7xq"),
        actor,
    )
    assert first.warning is None and first.code_used_by_lead_id is None
    assert (first.lead.channel, first.lead.utm_campaign) == ("meta_ads", "diwali")
    assert first.lead.enquiry_code_id == code.id

    second = svc.create_manual_lead(
        db, LeadCreate(location_id=loc.id, phone="9123456780", enquiry_code="W4K7XQ"), actor
    )
    assert second.code_used_by_lead_id == first.lead.id

    unknown = svc.create_manual_lead(
        db, LeadCreate(location_id=loc.id, phone="9000000001", enquiry_code="ZZZZZZ"), actor
    )
    assert unknown.warning and unknown.lead.channel == "manual"


def test_expired_enquiry_code_warns(db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin")
    db.commit()
    old = datetime.now(UTC) - timedelta(days=31)
    svc.register_enquiry_code(db, EnquiryCodeIn(code="ABCDEF"), now=old)
    result = svc.create_manual_lead(
        db, LeadCreate(location_id=loc.id, phone=PHONE, enquiry_code="ABCDEF"), _actor(admin)
    )
    assert result.warning is not None
    assert result.lead.enquiry_code_id is None


def test_enquiry_code_format_is_validated() -> None:
    for bad in ("ABC", "ABCDE0", "abcdeI", "ABCDEFG"):
        with pytest.raises(ValidationError):
            EnquiryCodeIn(code=bad)


def test_whatsapp_ad_source_gets_meta_channel(db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin")
    db.commit()
    lead = svc.create_manual_lead(
        db, LeadCreate(location_id=loc.id, phone=PHONE, source="whatsapp_ad"), _actor(admin)
    ).lead
    assert lead.channel == "meta_ads"


def test_detail_read_has_timeline_and_same_phone_leads(db: Session) -> None:
    a = make_location(db)
    b = make_location(db, name="Ecity")
    admin = make_user(db, "admin")
    staff_a = make_user(db, "staff", location_id=a.id)
    db.commit()
    lead_a = svc.create_manual_lead(
        db, LeadCreate(location_id=a.id, phone=PHONE, note="first"), _actor(admin)
    ).lead
    svc.create_manual_lead(db, LeadCreate(location_id=b.id, phone=PHONE), _actor(admin))

    as_admin = svc.get_lead(db, lead_a.id, _actor(admin))
    assert [x.location_id for x in as_admin.same_phone_leads] == [b.id]
    assert as_admin.activities[0].type in ("note", "system")
    as_staff = svc.get_lead(db, lead_a.id, _actor(staff_a))
    assert as_staff.same_phone_leads == []  # other branch hidden from staff (R6.3)
