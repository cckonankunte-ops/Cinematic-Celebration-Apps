"""Public lead endpoints (lead-crm group 5, real PostgreSQL).

Covers R2.1-R2.3, R2.12-R2.14, R3.2, R3.3, R3.7, R3.8, R11.6, R12.6, R15.2, R15.3,
R18.5-R18.7 and test cases R19.2, R19.3, R19.14, R19.16, R19.21:
- Step 1 capture returns a token; a second call with it updates the same lead;
- an invalid phone is a 422 and stores nothing;
- client-sent status / notes / assignment are ignored;
- enquiries and the legacy contact form create leads; the honeypot stores nothing;
- the rate limits return 429;
- enquiry codes register, re-register and reject bad formats;
- public responses carry no lead data; logs carry no phone or name;
- public locations expose ``whatsapp_phone``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import errors as errors_module
from app.models.contact_lead import ContactLead
from app.models.lead import EnquiryCode, Lead, LeadActivity
from app.services import leads as leads_service
from tests.factories import make_location

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}
PHONE = "9876543210"
NAME = "Priya Shankar"
CODE = "ABC234"


def _post(client: TestClient, path: str, body: dict):
    return client.post(f"/api/v1/public{path}", json=body, headers=_ORIGIN)


def _leads(db: Session) -> list[Lead]:
    db.expire_all()
    return list(db.execute(select(Lead).order_by(Lead.id)).scalars())


def _notes(db: Session, lead_id: int) -> list[str]:
    return [
        a.text or ""
        for a in db.execute(
            select(LeadActivity)
            .where(LeadActivity.lead_id == lead_id, LeadActivity.type == "note")
            .order_by(LeadActivity.id)
        ).scalars()
    ]


def _branch(db: Session, **kw) -> int:
    loc = make_location(db, **kw)
    db.commit()
    return loc.id


def _enquiry(loc_id: int, **extra) -> dict:
    return {
        "source": "homepage_form",
        "location_id": loc_id,
        "phone": PHONE,
        "name": NAME,
        **extra,
    }


# --- POST /leads (wizard Step 1) ------------------------------------------------


def test_step1_returns_token_and_second_call_updates_same_lead(
    client: TestClient, db: Session
) -> None:
    loc_id = _branch(db)
    first = _post(client, "/leads", {"location_id": loc_id, "phone": "+91 98765 43210"})
    assert first.status_code == 201, first.text
    assert set(first.json()) == {"lead_token"}
    token = first.json()["lead_token"]

    second = _post(
        client,
        "/leads",
        {"location_id": loc_id, "phone": PHONE, "lead_token": token, "name": NAME, "guests": 4},
    )
    assert second.status_code == 201
    assert second.json() == {"lead_token": token}

    leads = _leads(db)
    assert len(leads) == 1
    assert (leads[0].phone, leads[0].name, leads[0].guests) == (PHONE, NAME, 4)
    assert (leads[0].source, leads[0].status) == ("website", "new")


def test_step1_phone_change_corrects_the_same_lead(client: TestClient, db: Session) -> None:
    """A typo fix on Step 1 must not leave a second, wrong-number lead behind."""
    loc_id = _branch(db)
    token = _post(client, "/leads", {"location_id": loc_id, "phone": "9487578375"}).json()[
        "lead_token"
    ]
    again = _post(
        client, "/leads", {"location_id": loc_id, "phone": "9487576275", "lead_token": token}
    )
    assert again.status_code == 201
    assert again.json() == {"lead_token": token}

    leads = _leads(db)
    assert [(lead.phone, lead.status) for lead in leads] == [("9487576275", "new")]
    texts = [
        a.text
        for a in db.execute(
            select(LeadActivity).where(LeadActivity.lead_id == leads[0].id)
        ).scalars()
    ]
    assert f"{leads_service.PHONE_CORRECTED_TEXT} from +91 9487578375" in texts


def test_step1_phone_change_to_number_with_open_lead_continues_there(
    client: TestClient, db: Session
) -> None:
    loc_id = _branch(db)
    _post(client, "/enquiries", _enquiry(loc_id, phone="9487576275"))
    token = _post(client, "/leads", {"location_id": loc_id, "phone": "9487578375"}).json()[
        "lead_token"
    ]

    again = _post(
        client,
        "/leads",
        {"location_id": loc_id, "phone": "9487576275", "lead_token": token, "guests": 5},
    )
    assert again.status_code == 201
    new_token = again.json()["lead_token"]
    assert new_token != token

    by_phone = {lead.phone: lead for lead in _leads(db)}
    assert (by_phone["9487576275"].status, by_phone["9487576275"].guests) == ("new", 5)
    wrong = by_phone["9487578375"]
    assert (wrong.status, wrong.close_reason) == ("lost", "other")
    assert wrong.close_reason_text == leads_service.PHONE_CORRECTED_TEXT
    assert wrong.lead_token_hash is None
    right = by_phone["9487576275"]
    right_texts = [
        a.text or ""
        for a in db.execute(
            select(LeadActivity).where(LeadActivity.lead_id == right.id)
        ).scalars()
    ]
    assert any("from +91 9487578375" in t and f"lead #{wrong.id}" in t for t in right_texts)
    wrong_texts = [
        a.text or ""
        for a in db.execute(
            select(LeadActivity).where(LeadActivity.lead_id == wrong.id)
        ).scalars()
    ]
    assert f"Continued on lead #{right.id} for the corrected number" in wrong_texts

    # The new token keeps working on the right lead; the old one no longer does.
    third = _post(
        client,
        "/leads",
        {"location_id": loc_id, "phone": "9487576275", "lead_token": new_token},
    )
    assert third.json() == {"lead_token": new_token}
    assert sum(1 for lead in _leads(db) if lead.status == "new") == 1


def test_step1_invalid_phone_is_422_and_stores_nothing(client: TestClient, db: Session) -> None:
    loc_id = _branch(db)
    resp = _post(client, "/leads", {"location_id": loc_id, "phone": "12345"})
    assert resp.status_code == 422
    assert "error" in resp.json()
    assert _leads(db) == []


def test_step1_unknown_branch_is_422(client: TestClient, db: Session) -> None:
    resp = _post(client, "/leads", {"location_id": 999_999, "phone": PHONE})
    assert resp.status_code == 422
    assert _leads(db) == []


def test_client_cannot_set_status_notes_or_assignment(client: TestClient, db: Session) -> None:
    loc_id = _branch(db)
    resp = _post(
        client,
        "/leads",
        {
            "location_id": loc_id,
            "phone": PHONE,
            "status": "won",
            "notes": "VIP, free decor",
            "assigned_user_id": 1,
            "close_reason": "other",
            "source": "walk_in",
        },
    )
    assert resp.status_code == 201
    lead = _leads(db)[0]
    assert (lead.status, lead.source, lead.assigned_user_id) == ("new", "website", None)
    assert _notes(db, lead.id) == []


# --- POST /enquiries ------------------------------------------------------------


def test_enquiry_creates_lead_with_note(client: TestClient, db: Session) -> None:
    loc_id = _branch(db)
    resp = _post(
        client,
        "/enquiries",
        _enquiry(
            loc_id,
            message="Anniversary on Friday",
            email="p@example.com",
            attribution={"utm_source": "google", "utm_medium": "cpc", "gclid": "abc"},
        ),
    )
    assert resp.status_code == 201, resp.text
    assert set(resp.json()) == {"message"}

    lead = _leads(db)[0]
    assert (lead.source, lead.status, lead.channel) == ("homepage_form", "new", "google_ads")
    assert any("Anniversary on Friday" in n and "p@example.com" in n for n in _notes(db, lead.id))


def test_enquiry_honeypot_returns_success_and_stores_nothing(
    client: TestClient, db: Session
) -> None:
    loc_id = _branch(db)
    real = _post(client, "/enquiries", _enquiry(loc_id, phone="9123456780"))
    bot = _post(client, "/enquiries", _enquiry(loc_id, website="http://spam.example"))
    assert bot.status_code == 201
    assert bot.json() == real.json()
    assert [lead.phone for lead in _leads(db)] == ["9123456780"]


def test_enquiry_invalid_phone_is_422(client: TestClient, db: Session) -> None:
    loc_id = _branch(db)
    resp = _post(client, "/enquiries", _enquiry(loc_id, phone="98765"))
    assert resp.status_code == 422
    assert _leads(db) == []


# --- POST /contact (legacy) -------------------------------------------------------


def test_contact_form_creates_contact_form_lead(client: TestClient, db: Session) -> None:
    loc_id = _branch(db)
    resp = _post(
        client,
        "/contact",
        {"name": NAME, "phone": PHONE, "message": "Do you do proposals?", "location_id": loc_id},
    )
    assert resp.status_code == 201, resp.text
    assert set(resp.json()) == {"message"}

    lead = _leads(db)[0]
    assert (lead.source, lead.location_id) == ("contact_form", loc_id)
    assert not any("Branch unknown" in n for n in _notes(db, lead.id))
    # The legacy table is no longer written.
    assert db.execute(select(func.count()).select_from(ContactLead)).scalar_one() == 0


def test_contact_form_without_branch_uses_first_active_with_note(
    client: TestClient, db: Session
) -> None:
    _branch(db, name="Closed", is_active=False)
    first_active = _branch(db, name="Hulimavu")
    _branch(db, name="Ecity")
    resp = _post(
        client,
        "/contact",
        {"name": NAME, "phone": PHONE, "email": "", "message": "Hi"},
    )
    assert resp.status_code == 201, resp.text
    lead = _leads(db)[0]
    assert lead.location_id == first_active
    assert any("Branch unknown" in n for n in _notes(db, lead.id))


def test_contact_form_invalid_phone_is_422(client: TestClient, db: Session) -> None:
    _branch(db)
    resp = _post(client, "/contact", {"name": NAME, "phone": "abc", "message": "Hi"})
    assert resp.status_code == 422
    assert _leads(db) == []


# --- rate limits ------------------------------------------------------------------


@pytest.mark.parametrize(("path", "limit"), [("/leads", 10), ("/enquiries", 5)])
def test_rate_limits(client: TestClient, db: Session, path: str, limit: int) -> None:
    loc_id = _branch(db)
    body = (
        {"location_id": loc_id, "phone": PHONE}
        if path == "/leads"
        else _enquiry(loc_id)
    )
    codes = [_post(client, path, body).status_code for _ in range(limit + 1)]
    assert codes[:limit] == [201] * limit
    assert codes[limit] == 429


def test_enquiry_code_rate_limit(client: TestClient, db: Session) -> None:
    codes = [
        _post(client, "/enquiry-codes", {"code": CODE}).status_code for _ in range(11)
    ]
    assert codes[:10] == [204] * 10
    assert codes[10] == 429


# --- POST /enquiry-codes ------------------------------------------------------------


def test_enquiry_code_register_and_re_register(client: TestClient, db: Session) -> None:
    loc_a = _branch(db, name="Hulimavu")
    loc_b = _branch(db, name="Ecity")

    first = _post(
        client,
        "/enquiry-codes",
        {"code": CODE.lower(), "location_id": loc_a, "attribution": {"fbclid": "IwAR1"}},
    )
    assert first.status_code == 204
    assert first.content == b""
    db.expire_all()
    row = db.execute(select(EnquiryCode)).scalar_one()
    assert (row.code, row.location_id, row.channel) == (CODE, loc_a, "meta_ads")
    seen_first = row.last_seen_at

    again = _post(
        client,
        "/enquiry-codes",
        {"code": CODE, "location_id": loc_b, "attribution": {"utm_source": "google"}},
    )
    assert again.status_code == 204
    db.expire_all()
    row = db.execute(select(EnquiryCode)).scalar_one()
    # Branch and last-seen move; the first attribution is kept.
    assert (row.location_id, row.channel) == (loc_b, "meta_ads")
    assert row.last_seen_at >= seen_first
    assert _leads(db) == []


@pytest.mark.parametrize("bad", ["ABC12", "ABC2345", "ABCO23", "AB-234", ""])
def test_enquiry_code_invalid_format_is_422(client: TestClient, db: Session, bad: str) -> None:
    resp = _post(client, "/enquiry-codes", {"code": bad})
    assert resp.status_code == 422
    assert db.execute(select(func.count()).select_from(EnquiryCode)).scalar_one() == 0


# --- public locations -----------------------------------------------------------------


def test_public_locations_expose_whatsapp_phone(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    loc.whatsapp_phone = "9000000001"
    db.commit()
    body = client.get("/api/v1/public/locations").json()
    assert body[0]["whatsapp_phone"] == "9000000001"


# --- privacy ----------------------------------------------------------------------------


class _LogRecorder:
    """Stands in for structlog loggers (cached loggers bypass capsys)."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []

    def _record(self, event: str, **kw: object) -> None:
        self.records.append((event, kw))

    info = warning = error = exception = debug = _record


def test_lead_endpoint_logs_contain_no_phone_or_name(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    loc_id = _branch(db)
    recorder = _LogRecorder()
    monkeypatch.setattr(leads_service, "log", recorder)
    monkeypatch.setattr(errors_module, "log", recorder)

    token = _post(
        client, "/leads", {"location_id": loc_id, "phone": PHONE, "name": NAME}
    ).json()["lead_token"]
    _post(client, "/enquiries", _enquiry(loc_id, phone="9123456780", message="Call me"))
    _post(client, "/contact", {"name": NAME, "phone": "9988776655", "message": "Hi"})
    _post(client, "/enquiry-codes", {"code": CODE, "location_id": loc_id})

    assert any(event == "lead_created" for event, _ in recorder.records)
    logged = repr(recorder.records)
    for secret in (PHONE, "9123456780", "9988776655", NAME, "Call me", token):
        assert secret not in logged
