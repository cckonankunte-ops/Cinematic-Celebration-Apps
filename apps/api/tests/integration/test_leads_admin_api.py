"""Admin lead API (lead-crm group 6, real PostgreSQL).

Covers R5.1-R5.4, R5.8, R5.9, R10.1, R11.2, R11.6, R12.1-R12.5, R12.7, R13 and
test cases R19.12, R19.22:
- access control: 401 without a session; staff 403 on another branch, 200 on
  their own; staff 403 on the dashboard; admin 200; assignment to a user
  without branch access is 422;
- list ordering: uncontacted -> overdue -> due today -> new -> others;
- the uncontacted rule follows LEAD_RESPONSE_ALERT_MINUTES; badge counts;
- follow-up digest and assignable users;
- dashboard figures on seeded data;
- branch WhatsApp number on location settings.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ValidationFailedError
from app.core.security import CurrentUser
from app.models.lead import EnquiryCode, Lead, LeadActivity
from app.models.location import Location
from app.services import leads as leads_service
from app.services.leads import LeadListFilters
from tests.factories import make_location, make_user

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _alert_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the default so an ambient .env cannot change the expected sections."""
    monkeypatch.setattr(settings, "LEAD_RESPONSE_ALERT_MINUTES", 10)


_ORIGIN = {"Origin": "http://localhost:5173"}
# 12:00 IST on a fixed day, so "due today" never crosses midnight in a test run.
NOW = datetime(2026, 11, 10, 6, 30, tzinfo=UTC)
NOW_IST_DATE = date(2026, 11, 10)
_phones = count(1)


def _phone() -> str:
    return f"98{next(_phones):08d}"


def _lead(db: Session, location_id: int, **kw) -> Lead:
    created = kw.pop("created_at", NOW - timedelta(days=2))
    lead = Lead(
        location_id=location_id,
        phone=kw.pop("phone", _phone()),
        source=kw.pop("source", "whatsapp"),
        channel=kw.pop("channel", "manual"),
        status=kw.pop("status", "new"),
        created_at=created,
        last_activity_at=kw.pop("last_activity_at", created),
        **kw,
    )
    db.add(lead)
    db.flush()
    return lead


def _admin_actor() -> CurrentUser:
    return CurrentUser(id=1, username="admin", role="admin", location_id=None)


def _login(client: TestClient, username: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200, resp.text


def _get(client: TestClient, path: str, **params):
    return client.get(f"/api/v1/admin{path}", params=params, headers=_ORIGIN)


# --- access control (R12) ---------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/leads", "/leads/counts", "/leads/follow-ups", "/leads/dashboard", "/leads/1"],
)
def test_lead_endpoints_need_a_session(client: TestClient, path: str) -> None:
    assert client.get(f"/api/v1/admin{path}", headers=_ORIGIN).status_code == 401


def test_create_needs_a_session(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/admin/leads", json={"location_id": 1, "phone": "9876543210"}, headers=_ORIGIN
    )
    assert resp.status_code == 401


def test_receptionist_sees_only_own_branch(client: TestClient, db: Session) -> None:
    own = make_location(db, name="Hulimavu")
    other = make_location(db, name="Ecity")
    staff = make_user(db, "receptionist", location_id=own.id)
    mine = _lead(db, own.id)
    theirs = _lead(db, other.id)
    db.commit()
    _login(client, staff.username)

    assert _get(client, f"/leads/{mine.id}").status_code == 200
    assert _get(client, f"/leads/{theirs.id}").status_code == 403

    listed = _get(client, "/leads").json()
    assert [item["id"] for item in listed["items"]] == [mine.id]
    assert _get(client, "/leads", location_id=other.id).status_code == 403
    assert _get(client, "/leads/counts", location_id=other.id).status_code == 403

    patch = client.patch(
        f"/api/v1/admin/leads/{theirs.id}", json={"name": "X"}, headers=_ORIGIN
    )
    assert patch.status_code == 403
    note = client.post(
        f"/api/v1/admin/leads/{theirs.id}/activities", json={"type": "note"}, headers=_ORIGIN
    )
    assert note.status_code == 403
    create = client.post(
        "/api/v1/admin/leads",
        json={"location_id": other.id, "phone": "9123456780"},
        headers=_ORIGIN,
    )
    assert create.status_code == 403


def test_receptionist_cannot_open_dashboard_admin_can(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    staff = make_user(db, "receptionist", location_id=loc.id)
    admin = make_user(db, "admin")
    db.commit()

    _login(client, staff.username)
    assert _get(client, "/leads/dashboard").status_code == 403

    _login(client, admin.username)
    resp = _get(client, "/leads/dashboard", location_id=loc.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 0


def test_admin_reads_any_branch(client: TestClient, db: Session) -> None:
    a = make_location(db, name="Hulimavu")
    b = make_location(db, name="Ecity")
    admin = make_user(db, "admin")
    la, lb = _lead(db, a.id), _lead(db, b.id)
    db.commit()
    _login(client, admin.username)
    assert _get(client, f"/leads/{lb.id}").status_code == 200
    assert {i["id"] for i in _get(client, "/leads").json()["items"]} == {la.id, lb.id}


def test_assignment_rules(client: TestClient, db: Session) -> None:
    own = make_location(db, name="Hulimavu")
    other = make_location(db, name="Ecity")
    staff = make_user(db, "receptionist", location_id=own.id)
    colleague = make_user(db, "receptionist", location_id=own.id)
    outsider = make_user(db, "receptionist", location_id=other.id)
    inactive = make_user(db, "receptionist", location_id=own.id, is_active=False)
    admin = make_user(db, "admin")
    lead = _lead(db, own.id)
    db.commit()
    _login(client, staff.username)

    def assign(user_id: int | None) -> int:
        return client.patch(
            f"/api/v1/admin/leads/{lead.id}",
            json={"assigned_user_id": user_id},
            headers=_ORIGIN,
        ).status_code

    assert assign(outsider.id) == 422
    assert assign(inactive.id) == 422
    assert assign(colleague.id) == 200
    assert assign(admin.id) == 200
    assert assign(None) == 200

    users = _get(client, "/leads/assignable-users", location_id=own.id).json()
    assert {u["id"] for u in users} == {staff.id, colleague.id, admin.id}
    assert _get(client, "/leads/assignable-users", location_id=other.id).status_code == 403


def test_create_detail_activity_flow_over_http(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    staff = make_user(db, "receptionist", location_id=loc.id)
    db.commit()
    _login(client, staff.username)

    created = client.post(
        "/api/v1/admin/leads",
        json={"location_id": loc.id, "phone": "+91 98765 43210", "name": "Asha", "note": "DM"},
        headers=_ORIGIN,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["created"] is True and body["lead"]["phone"] == "9876543210"
    lead_id = body["lead"]["id"]

    act = client.post(
        f"/api/v1/admin/leads/{lead_id}/activities",
        json={"type": "call", "text": "No answer"},
        headers=_ORIGIN,
    )
    assert act.status_code == 201
    assert act.json()["status"] == "contacted"

    booked = client.patch(
        f"/api/v1/admin/leads/{lead_id}", json={"status": "won"}, headers=_ORIGIN
    )
    assert booked.status_code == 422

    detail = _get(client, f"/leads/{lead_id}").json()
    assert [a["type"] for a in detail["activities"]][:1] == ["call"]


# --- list ordering, uncontacted rule, counts (R5.1, R5.8, R5.9, R10.1) ---------------


def _seed_sections(db: Session) -> tuple[int, dict[str, int]]:
    loc = make_location(db)
    other = make_location(db, name="Ecity")
    m = NOW - timedelta(minutes=1)  # a minute, for readability below
    ids = {
        "u_old": _lead(db, loc.id, created_at=NOW - timedelta(minutes=60)).id,
        "u_older": _lead(db, loc.id, created_at=NOW - timedelta(minutes=120)).id,
        "fresh_new": _lead(db, loc.id, created_at=NOW - timedelta(minutes=5)).id,
        "fresh_new_2": _lead(db, loc.id, created_at=NOW - timedelta(minutes=8)).id,
        "overdue_1": _lead(
            db, loc.id, status="follow_up", follow_up_at=NOW - timedelta(hours=2),
            last_activity_at=m,
        ).id,
        "overdue_2": _lead(
            db, loc.id, status="follow_up", follow_up_at=NOW - timedelta(minutes=30),
        ).id,
        "due_1": _lead(
            db, loc.id, status="follow_up", follow_up_at=NOW + timedelta(hours=1)
        ).id,
        "due_2": _lead(
            db, loc.id, status="follow_up", follow_up_at=NOW + timedelta(hours=3)
        ).id,
        "tomorrow": _lead(
            db, loc.id, status="follow_up", follow_up_at=NOW + timedelta(days=1),
            last_activity_at=NOW - timedelta(minutes=30),
        ).id,
        "contacted": _lead(
            db, loc.id, status="contacted", first_contacted_at=NOW - timedelta(hours=1),
            last_activity_at=NOW - timedelta(minutes=10),
        ).id,
        "lost": _lead(
            db, loc.id, status="lost", close_reason="other",
            last_activity_at=NOW - timedelta(days=1),
        ).id,
    }
    _lead(db, other.id, created_at=NOW - timedelta(hours=5))  # other branch, uncontacted
    db.commit()
    return loc.id, ids


def _order(db: Session, location_id: int, **kw) -> list[int]:
    page = leads_service.list_leads(
        db, _admin_actor(), LeadListFilters(location_id=location_id, **kw), now=NOW
    )
    return [item.id for item in page.items]


def test_list_section_ordering(db: Session) -> None:
    loc_id, ids = _seed_sections(db)
    expected = [
        "u_older", "u_old",            # 1 uncontacted, oldest first
        "overdue_1", "overdue_2",      # 2 overdue, oldest follow-up first
        "due_1", "due_2",              # 3 due today, soonest first
        "fresh_new", "fresh_new_2",    # 4 new, newest first
        "contacted", "tomorrow", "lost",  # 5 others, latest activity first
    ]
    assert _order(db, loc_id) == [ids[k] for k in expected]


def test_list_pagination_is_stable(db: Session) -> None:
    loc_id, _ = _seed_sections(db)
    full = _order(db, loc_id)
    pages = _order(db, loc_id, limit=4) + _order(db, loc_id, limit=4, offset=4) + _order(
        db, loc_id, limit=4, offset=8
    )
    assert pages == full
    page = leads_service.list_leads(
        db, _admin_actor(), LeadListFilters(location_id=loc_id, limit=4), now=NOW
    )
    assert page.total == 11


def test_uncontacted_rule_follows_alert_minutes(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    loc_id, ids = _seed_sections(db)
    counts = leads_service.lead_counts(db, _admin_actor(), loc_id, now=NOW)
    assert (counts.uncontacted, counts.overdue, counts.due_today) == (2, 2, 2)

    monkeypatch.setattr(settings, "LEAD_RESPONSE_ALERT_MINUTES", 90)
    counts = leads_service.lead_counts(db, _admin_actor(), loc_id, now=NOW)
    assert counts.uncontacted == 1
    order = _order(db, loc_id)
    assert order[0] == ids["u_older"]
    # u_old (60 min) is now an ordinary new lead, the oldest of the "new" section.
    assert order.index(ids["u_old"]) == order.index(ids["fresh_new_2"]) + 1

    monkeypatch.setattr(settings, "LEAD_RESPONSE_ALERT_MINUTES", 1)
    counts = leads_service.lead_counts(db, _admin_actor(), loc_id, now=NOW)
    assert counts.uncontacted == 4


def test_counts_for_all_branches_and_list_reads_flag(db: Session) -> None:
    loc_id, ids = _seed_sections(db)
    everywhere = leads_service.lead_counts(db, _admin_actor(), None, now=NOW)
    assert everywhere.uncontacted == 3
    page = leads_service.list_leads(
        db, _admin_actor(), LeadListFilters(location_id=loc_id), now=NOW
    )
    flags = {item.id: item.is_uncontacted for item in page.items}
    assert flags[ids["u_old"]] and not flags[ids["fresh_new"]]


def test_list_filters_and_search(db: Session) -> None:
    loc = make_location(db)
    asha = _lead(db, loc.id, name="Asha Rao", phone="9876500001", source="website",
                 channel="meta_ads")
    _lead(db, loc.id, name="Ravi", phone="9123400002", status="contacted")
    db.commit()

    assert _order(db, loc.id, q="asha") == [asha.id]
    assert _order(db, loc.id, q="500001") == [asha.id]
    assert _order(db, loc.id, statuses=("new",), sources=("website",)) == [asha.id]
    assert _order(db, loc.id, channels=("meta_ads",)) == [asha.id]
    assert _order(db, loc.id, q="%%%") == []
    with pytest.raises(ValidationFailedError):
        _order(db, loc.id, q="as")


# --- follow-up digest (R11.2) -------------------------------------------------------


def test_follow_up_digest(db: Session) -> None:
    loc = make_location(db)
    late = _lead(db, loc.id, name="Late", status="follow_up",
                 follow_up_at=NOW - timedelta(hours=1))
    soon = _lead(db, loc.id, status="follow_up", follow_up_at=NOW + timedelta(hours=2))
    _lead(db, loc.id, status="follow_up", follow_up_at=NOW + timedelta(days=2))
    db.add_all(
        [
            LeadActivity(lead_id=late.id, type="note", text="old note",
                         created_at=NOW - timedelta(days=1)),
            LeadActivity(lead_id=late.id, type="note", text="x" * 100,
                         created_at=NOW - timedelta(hours=2)),
        ]
    )
    db.commit()

    digest = leads_service.follow_up_digest(db, _admin_actor(), loc.id, now=NOW)
    assert [i.id for i in digest.items] == [late.id, soon.id]
    assert digest.items[0].is_overdue and not digest.items[1].is_overdue
    assert digest.items[0].last_note == "x" * 60
    assert digest.items[1].last_note is None


# --- dashboard (R13) ------------------------------------------------------------------


def test_dashboard_figures(db: Session) -> None:
    loc = make_location(db)
    other = make_location(db, name="Ecity")
    code = EnquiryCode(code="ABC234", channel="direct", created_at=NOW, last_seen_at=NOW)
    db.add(code)
    db.flush()
    t0 = NOW - timedelta(hours=3)

    def contacted(minutes: int) -> datetime:
        return t0 + timedelta(minutes=minutes)

    _lead(db, loc.id, source="website", channel="meta_ads", status="won", created_at=t0,
          first_contacted_at=contacted(10), utm_campaign="diwali")
    _lead(db, loc.id, source="website", channel="meta_ads", status="lost",
          close_reason="price_budget", created_at=t0, first_contacted_at=contacted(30),
          utm_campaign="diwali")
    _lead(db, loc.id, source="whatsapp", channel="manual", created_at=t0,
          first_contacted_at=contacted(20), enquiry_code_id=code.id)
    _lead(db, loc.id, source="whatsapp_ad", channel="meta_ads", status="not_interested",
          close_reason="just_enquiring", created_at=t0)
    _lead(db, loc.id, source="homepage_form", channel="direct",
          created_at=NOW - timedelta(days=40))  # outside the range
    _lead(db, other.id, source="website", channel="google_ads", created_at=t0)
    db.commit()

    d = leads_service.dashboard(
        db, _admin_actor(), location_id=loc.id,
        date_from=NOW_IST_DATE - timedelta(days=6), date_to=NOW_IST_DATE,
    )
    assert (d.total, d.won) == (4, 1)
    assert {(r.key, r.total, r.won) for r in d.by_source} == {
        ("website", 2, 1), ("whatsapp", 1, 0), ("whatsapp_ad", 1, 0)
    }
    assert {(r.key, r.total, r.won) for r in d.by_channel} == {
        ("meta_ads", 3, 1), ("manual", 1, 0)
    }
    assert {(r.day, r.key, r.count) for r in d.per_day_by_channel} == {
        (NOW_IST_DATE, "meta_ads", 3), (NOW_IST_DATE, "manual", 1)
    }
    assert sum(r.count for r in d.per_day_by_source) == 4
    assert (d.contacted, d.avg_first_response_minutes, d.median_first_response_minutes) == (
        3, 20, 20
    )
    assert {(r.reason, r.count) for r in d.close_reasons} == {
        ("price_budget", 1), ("just_enquiring", 1)
    }
    assert [(r.key, r.total, r.won) for r in d.campaigns] == [("diwali", 2, 1)]
    assert (d.whatsapp_total, d.whatsapp_with_code) == (2, 1)

    everywhere = leads_service.dashboard(
        db, _admin_actor(), location_id=None,
        date_from=NOW_IST_DATE, date_to=NOW_IST_DATE,
    )
    assert everywhere.total == 5


def test_dashboard_rejects_bad_ranges(db: Session) -> None:
    with pytest.raises(ValidationFailedError):
        leads_service.dashboard(
            db, _admin_actor(), location_id=None,
            date_from=NOW_IST_DATE, date_to=NOW_IST_DATE - timedelta(days=1),
        )


# --- branch WhatsApp number (R11.6) ----------------------------------------------------


def test_location_whatsapp_phone_setting(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    admin = make_user(db, "admin")
    db.commit()
    _login(client, admin.username)
    url = f"/api/v1/admin/locations/{loc.id}"

    ok = client.patch(url, json={"whatsapp_phone": "+91 90000 00001"}, headers=_ORIGIN)
    assert ok.status_code == 200, ok.text
    assert ok.json()["whatsapp_phone"] == "9000000001"

    bad = client.patch(url, json={"whatsapp_phone": "12345"}, headers=_ORIGIN)
    assert bad.status_code == 422

    cleared = client.patch(url, json={"whatsapp_phone": None}, headers=_ORIGIN)
    assert cleared.status_code == 200
    db.expire_all()
    assert db.get(Location, loc.id).whatsapp_phone is None
