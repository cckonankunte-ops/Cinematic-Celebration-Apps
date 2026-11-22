"""Auto-close stale leads (lead-crm group 7, real PostgreSQL).

Covers R14.1-R14.8 and test case R19.13:
- with 14 days, stale new / contacted / follow_up leads close as lost/no_response
  with a system activity;
- booked leads, leads with a future follow-up, and recently active leads stay open;
- a second run changes nothing; with 0 days nothing closes;
- the CLI job reads LEAD_AUTO_CLOSE_DAYS on each run and logs the count only;
- property 8: running twice equals running once.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.jobs import auto_close_leads as job
from app.models.lead import Lead, LeadActivity
from app.services.leads import close_stale_leads
from tests.factories import make_location

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 10, 6, 30, tzinfo=UTC)
_phones = count(1)


def _lead(db: Session, location_id: int, *, idle_days: float, **kw) -> Lead:
    last = NOW - timedelta(days=idle_days)
    lead = Lead(
        location_id=location_id,
        phone=f"97{next(_phones):08d}",
        source="whatsapp",
        channel="manual",
        status=kw.pop("status", "new"),
        created_at=last,
        last_activity_at=last,
        **kw,
    )
    db.add(lead)
    db.flush()
    return lead


def _statuses(db: Session, ids: dict[str, int]) -> dict[str, tuple[str, str | None]]:
    db.expire_all()
    out = {}
    for key, lead_id in ids.items():
        lead = db.get(Lead, lead_id)
        assert lead is not None
        out[key] = (lead.status, lead.close_reason)
    return out


def _seed(db: Session) -> dict[str, int]:
    loc = make_location(db)
    ids = {
        "stale_new": _lead(db, loc.id, idle_days=20).id,
        "stale_contacted": _lead(db, loc.id, idle_days=15, status="contacted").id,
        "stale_follow_up_past": _lead(
            db, loc.id, idle_days=30, status="follow_up",
            follow_up_at=NOW - timedelta(days=16),
        ).id,
        "stale_follow_up_future": _lead(
            db, loc.id, idle_days=30, status="follow_up",
            follow_up_at=NOW + timedelta(days=1),
        ).id,
        "stale_booked": _lead(db, loc.id, idle_days=40, status="booked").id,
        "recent_new": _lead(db, loc.id, idle_days=13).id,
        "already_lost": _lead(
            db, loc.id, idle_days=60, status="lost", close_reason="price_budget"
        ).id,
    }
    db.commit()
    return ids


def test_closes_stale_leads_after_14_days(db: Session) -> None:
    ids = _seed(db)
    assert close_stale_leads(db, now=NOW, days=14) == 3

    got = _statuses(db, ids)
    for key in ("stale_new", "stale_contacted", "stale_follow_up_past"):
        assert got[key] == ("lost", "no_response"), key
    assert got["stale_follow_up_future"] == ("follow_up", None)
    assert got["stale_booked"] == ("booked", None)
    assert got["recent_new"] == ("new", None)
    assert got["already_lost"] == ("lost", "price_budget")

    closed = db.get(Lead, ids["stale_follow_up_past"])
    assert closed is not None and closed.follow_up_at is None
    texts = db.execute(
        select(LeadActivity.text).where(
            LeadActivity.lead_id == ids["stale_new"], LeadActivity.type == "system"
        )
    ).scalars().all()
    assert "Closed automatically after 14 days without activity" in texts


def test_second_run_changes_nothing(db: Session) -> None:
    _seed(db)
    assert close_stale_leads(db, now=NOW, days=14) == 3
    activities = db.execute(select(func.count()).select_from(LeadActivity)).scalar_one()
    assert close_stale_leads(db, now=NOW, days=14) == 0
    assert close_stale_leads(db, now=NOW + timedelta(hours=1), days=14) == 0
    after = db.execute(select(func.count()).select_from(LeadActivity)).scalar_one()
    assert after == activities


def test_zero_days_closes_nothing(db: Session) -> None:
    ids = _seed(db)
    assert close_stale_leads(db, now=NOW, days=0) == 0
    assert all(reason != "no_response" for _, reason in _statuses(db, ids).values())
    assert db.execute(select(func.count()).select_from(LeadActivity)).scalar_one() == 0


class _LogRecorder:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []

    def info(self, event: str, **kw: object) -> None:
        self.records.append((event, kw))


def test_job_reads_setting_each_run_and_logs_count_only(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    loc = make_location(db)
    # Real "now" for the job: idle well past any threshold used below.
    lead = Lead(
        location_id=loc.id, phone="9700000099", name="Asha", source="whatsapp",
        channel="manual", created_at=datetime.now(UTC) - timedelta(days=30),
        last_activity_at=datetime.now(UTC) - timedelta(days=30),
    )
    db.add(lead)
    db.commit()
    recorder = _LogRecorder()
    monkeypatch.setattr(job, "log", recorder)
    monkeypatch.setattr(job, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    monkeypatch.setattr(app_settings, "LEAD_AUTO_CLOSE_DAYS", 0)
    assert job.main() == 0
    monkeypatch.setattr(app_settings, "LEAD_AUTO_CLOSE_DAYS", 14)
    assert job.main() == 1

    assert recorder.records == [
        ("auto_close_leads_completed", {"closed": 0}),
        ("auto_close_leads_completed", {"closed": 1}),
    ]
    assert "9700000099" not in repr(recorder.records) and "Asha" not in repr(
        recorder.records
    )


@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    idle=st.lists(st.integers(min_value=0, max_value=60), min_size=1, max_size=6),
    days=st.integers(min_value=0, max_value=30),
)
def test_property_idempotent(db: Session, idle: list[int], days: int) -> None:
    """Property 8: a second run right after the first closes nothing."""
    loc = make_location(db)
    for d in idle:
        _lead(db, loc.id, idle_days=d)
    db.commit()
    close_stale_leads(db, now=NOW, days=days)

    def lost_here() -> int:
        return db.execute(
            select(func.count())
            .select_from(Lead)
            .where(Lead.location_id == loc.id, Lead.status == "lost")
        ).scalar_one()

    # Examples share the test DB, so count only this example's branch.
    expected = 0 if days == 0 else sum(1 for d in idle if d > days)
    assert lost_here() == expected
    assert close_stale_leads(db, now=NOW, days=days) == 0
    assert lost_here() == expected
