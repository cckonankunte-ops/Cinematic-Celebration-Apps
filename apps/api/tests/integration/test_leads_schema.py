"""Lead CRM schema (lead-crm group 1, real PostgreSQL).

- Contact-lead copy (R3.9-R3.11, R19.15): rows become ``contact_form`` leads with
  the original time and a first note; invalid phones are skipped; repeat phones
  attach to one lead; contact_leads is left untouched.
- Database guards: one pre-booking open lead per (branch, phone) (R6.4); closed
  leads need a reason and no follow-up (R1.8, R1.9); phone must be 10 digits.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.contact_lead import ContactLead
from app.models.lead import Lead, LeadActivity
from app.services.lead_migration import copy_contact_leads
from tests.factories import make_location

pytestmark = pytest.mark.integration


def _lead(location_id: int, phone: str = "9876543210", **kw) -> Lead:
    return Lead(location_id=location_id, phone=phone, source="whatsapp", **kw)


def test_copy_contact_leads(db: Session) -> None:
    make_location(db, name="Inactive", is_active=False)
    loc = make_location(db)
    t1 = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 2, 11, 0, tzinfo=UTC)
    t3 = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    db.add_all(
        [
            ContactLead(name="Asha", phone="+91 98765 43210", email="a@example.com",
                        message="Birthday on 5th", created_at=t1),
            ContactLead(name="Asha again", phone="09876543210", email="",
                        message="Any update?", created_at=t2),
            ContactLead(name="Bad", phone="12345", email="", message="x", created_at=t3),
        ]
    )
    db.flush()

    result = copy_contact_leads(db.connection())

    assert (result.copied, result.attached, result.skipped) == (1, 1, 1)
    leads = db.execute(select(Lead)).scalars().all()
    assert len(leads) == 1
    lead = leads[0]
    assert lead.location_id == loc.id  # first ACTIVE branch
    assert lead.phone == "9876543210"
    assert lead.source == "contact_form"
    assert lead.status == "new"
    assert lead.channel == "direct"
    assert lead.name == "Asha"
    assert lead.created_at == t1
    assert lead.last_activity_at == t2

    notes = db.execute(
        select(LeadActivity).where(LeadActivity.lead_id == lead.id).order_by(LeadActivity.id)
    ).scalars().all()
    assert [n.type for n in notes] == ["note", "note"]
    assert "Birthday on 5th" in notes[0].text
    assert "Email: a@example.com" in notes[0].text
    assert "Branch unknown (migrated)" in notes[0].text
    assert notes[0].created_at == t1
    assert "Any update?" in notes[1].text
    # The legacy table is untouched.
    assert db.execute(select(func.count()).select_from(ContactLead)).scalar() == 3


def test_copy_with_no_active_branch_copies_nothing(db: Session) -> None:
    make_location(db, is_active=False)
    db.add(ContactLead(name="A", phone="9876543210", email="", message="hi"))
    db.flush()
    result = copy_contact_leads(db.connection())
    assert (result.copied, result.attached, result.skipped) == (0, 0, 0)
    assert db.execute(select(func.count()).select_from(Lead)).scalar() == 0


def test_one_prebooking_open_lead_per_phone_and_branch(db: Session) -> None:
    loc = make_location(db)
    db.add(_lead(loc.id))
    db.flush()
    db.add(_lead(loc.id, status="follow_up", follow_up_at=datetime.now(UTC)))
    with pytest.raises(IntegrityError):
        db.flush()


def test_booked_and_closed_leads_do_not_block_a_new_open_lead(db: Session) -> None:
    loc = make_location(db)
    other = make_location(db, name="Ecity")
    db.add_all(
        [
            _lead(loc.id, status="booked"),
            _lead(loc.id, status="lost", close_reason="no_response"),
            _lead(loc.id, status="new"),
            _lead(other.id, status="new"),  # same phone, other branch
        ]
    )
    db.flush()
    assert db.execute(select(func.count()).select_from(Lead)).scalar() == 4


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "lost"},  # closed without a reason
        {"status": "not_interested"},
        {"status": "won", "follow_up_at": datetime.now(UTC)},  # closed with follow-up
        {"phone": "12345"},
        {"phone": "5876543210"},  # must start with 6-9
        {"source": "unknown"},
        {"channel": "tv"},
    ],
)
def test_lead_check_constraints(db: Session, fields: dict) -> None:
    loc = make_location(db)
    params = {"phone": "9876543210", **fields}
    db.add(Lead(location_id=loc.id, source=fields.get("source", "whatsapp"),
                **{k: v for k, v in params.items() if k != "source"}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_activity_type_is_checked(db: Session) -> None:
    loc = make_location(db)
    lead = _lead(loc.id)
    db.add(lead)
    db.flush()
    db.add(LeadActivity(lead_id=lead.id, type="email"))
    with pytest.raises(IntegrityError):
        db.flush()
