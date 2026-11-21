"""Lead CRM business rules (lead-crm).

All lead status changes go through ``_transition``; every timeline entry goes
through ``_add_activity`` (which keeps ``last_activity_at`` current). Duplicate
handling is ``_find_or_create_lead``, made race-safe by the partial unique index
``uq_leads_prebooking_phone``.

Privacy: logs carry only codes, ids and counts, never phone, name, note text,
message, IP or token (R15.2).
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Date, and_, case, cast, extract, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (
    ForbiddenError,
    LocationAccessDeniedError,
    NotFoundError,
    ValidationFailedError,
)
from app.core.logging import get_logger
from app.core.phone import normalize_indian_mobile
from app.core.security import CurrentUser, assert_location_access
from app.models.booking import Booking
from app.models.lead import (
    CLOSED_LEAD_STATUSES,
    PREBOOKING_LEAD_STATUSES,
    TEXT_MAX,
    EnquiryCode,
    Lead,
    LeadActivity,
)
from app.models.location import Location
from app.models.plan import Plan
from app.models.user import User
from app.models.user_role import UserRole
from app.schemas.booking import ContactCreate
from app.schemas.lead import (
    ActivityCreate,
    ActivityRead,
    AssignableUser,
    AttributionIn,
    AttributionSummary,
    DashboardDayRow,
    DashboardGroupRow,
    DashboardReasonRow,
    EnquiryCodeIn,
    EnquiryIn,
    FollowUpDigest,
    FollowUpItem,
    LeadBrief,
    LeadCounts,
    LeadCreate,
    LeadCreateResult,
    LeadDashboard,
    LeadListPage,
    LeadRead,
    LeadUpdate,
    WebsiteLeadIn,
)
from app.services.lead_channel import (
    Attribution,
    clean_attribution,
    derive_channel,
    host_of,
    manual_channel,
)

log = get_logger("app.services.leads")

LEAD_TOKEN_MAX_AGE = timedelta(days=7)
ENQUIRY_CODE_MAX_AGE = timedelta(days=30)
# Manual status targets (R7.5). `booked` / `won` only come from bookings (R7.7).
MANUAL_STATUS_TARGETS = ("new", "contacted", "follow_up", "not_interested", "lost")
# Statuses that follow a linked booking and cannot be changed by hand.
BOOKING_DRIVEN_STATUSES = ("booked", "won")
_ATTRIBUTION_FIELDS = tuple(f.name for f in fields(Attribution))
_ENQUIRY_FIELDS = (
    "name",
    "preferred_date",
    "plan_id",
    "start_time",
    "duration_minutes",
    "guests",
    "message",
)
_SOURCE_LABELS = {
    "website": "website booking form",
    "homepage_form": "homepage enquiry form",
    "contact_form": "contact page form",
    "whatsapp": "WhatsApp",
    "whatsapp_ad": "WhatsApp (from ad)",
    "phone": "phone call",
    "walk_in": "walk-in",
    "instagram_dm": "Instagram DM",
    "other": "other",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _own_hosts() -> frozenset[str]:
    hosts = {host_of(origin) for origin in settings.cors_origins}
    return frozenset(h for h in hosts if h)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_lead_token() -> str:
    """Opaque URL-safe token, 192 bits (A3). Only its hash is stored."""
    return secrets.token_urlsafe(24)


# --- low-level helpers ------------------------------------------------------


def _add_activity(
    db: Session,
    lead: Lead,
    type_: str,
    *,
    text: str | None = None,
    data: dict[str, Any] | None = None,
    author_id: int | None = None,
    now: datetime,
) -> LeadActivity:
    activity = LeadActivity(
        lead_id=lead.id,
        type=type_,
        text=text,
        data=data,
        author_user_id=author_id,
        created_at=now,
    )
    db.add(activity)
    if lead.last_activity_at is None or now >= lead.last_activity_at:
        lead.last_activity_at = now
    db.flush()
    return activity


def _transition(
    db: Session,
    lead: Lead,
    to_status: str,
    *,
    now: datetime,
    author_id: int | None = None,
    reason: str | None = None,
    reason_text: str | None = None,
    note: str | None = None,
) -> None:
    """The only place that changes ``lead.status`` (R1.6, R1.8, R1.9, R7.4)."""
    from_status = lead.status
    if to_status == from_status:
        return
    if to_status in ("lost", "not_interested"):
        if reason is None:
            raise ValidationFailedError("A close reason is required.")
        lead.close_reason = reason
        lead.close_reason_text = reason_text
    else:
        lead.close_reason = None
        lead.close_reason_text = None
    if to_status in CLOSED_LEAD_STATUSES:
        lead.follow_up_at = None
    if (
        author_id is not None
        and from_status == "new"
        and lead.first_contacted_at is None
    ):
        lead.first_contacted_at = now
    lead.status = to_status
    db.flush()
    _add_activity(
        db,
        lead,
        "status_change",
        text=note,
        data={"from": from_status, "to": to_status},
        author_id=author_id,
        now=now,
    )


def _has_attribution(lead: Lead) -> bool:
    return any(getattr(lead, name) is not None for name in _ATTRIBUTION_FIELDS)


def _apply_attribution(target: Lead | EnquiryCode, a: Attribution) -> None:
    for name in _ATTRIBUTION_FIELDS:
        setattr(target, name, getattr(a, name))


def _location_or_422(db: Session, location_id: int) -> Location:
    location = db.get(Location, location_id)
    if location is None or not location.is_active:
        raise ValidationFailedError("Unknown branch.")
    return location


def _valid_plan_id(db: Session, plan_id: int | None, location_id: int) -> int | None:
    if plan_id is None:
        return None
    plan = db.get(Plan, plan_id)
    return plan.id if plan is not None and plan.location_id == location_id else None


def _select_open_lead(
    db: Session, location_id: int, phone: str, statuses: tuple[str, ...]
) -> Lead | None:
    return db.execute(
        select(Lead)
        .where(
            Lead.location_id == location_id,
            Lead.phone == phone,
            Lead.status.in_(statuses),
        )
        .order_by(Lead.created_at.desc(), Lead.id.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()


@dataclass(frozen=True)
class _NewLead:
    location_id: int
    phone: str
    source: str
    channel: str
    fields: dict[str, Any]
    attribution: Attribution | None
    author_id: int | None


def _attach(db: Session, lead: Lead, new: _NewLead, now: datetime) -> None:
    """R6.1: repeat enquiry on an existing open lead — note it, fill only gaps."""
    for name, value in new.fields.items():
        if value is not None and getattr(lead, name) is None:
            setattr(lead, name, value)
    if new.attribution is not None and not _has_attribution(lead):
        _apply_attribution(lead, new.attribution)
        if lead.channel in ("direct", "manual"):
            lead.channel = new.channel
    label = _SOURCE_LABELS.get(new.source, new.source)
    _add_activity(
        db,
        lead,
        "system",
        text=f"Repeat enquiry via {label}",
        data={"source": new.source},
        author_id=new.author_id,
        now=now,
    )


def _insert_prebooking_lead(db: Session, new: _NewLead, now: datetime) -> int | None:
    values: dict[str, Any] = {
        "location_id": new.location_id,
        "phone": new.phone,
        "source": new.source,
        "status": "new",
        "channel": new.channel,
        "last_activity_at": now,
        "created_at": now,
        "updated_at": now,
        **{k: v for k, v in new.fields.items() if v is not None},
    }
    if new.attribution is not None:
        values.update(
            {name: getattr(new.attribution, name) for name in _ATTRIBUTION_FIELDS}
        )
    stmt = (
        pg_insert(Lead)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=["location_id", "phone"],
            index_where=Lead.status.in_(PREBOOKING_LEAD_STATUSES),
        )
        .returning(Lead.id)
    )
    return db.execute(stmt).scalar_one_or_none()


def _find_or_create_lead(
    db: Session,
    new: _NewLead,
    *,
    now: datetime,
    attach_to_booked: bool,
) -> tuple[Lead, bool]:
    """Duplicate rule (R6). Returns (lead, created).

    1. a pre-booking open lead for (branch, phone) -> attach;
    2. else, when allowed, a ``booked`` lead -> attach (enquiries, not bookings);
    3. else insert; a concurrent insert that won the unique index makes ours a
       no-op, so re-select and attach to that one (R6.4).
    """
    for _ in range(3):
        existing = _select_open_lead(db, new.location_id, new.phone, PREBOOKING_LEAD_STATUSES)
        if existing is None and attach_to_booked:
            existing = _select_open_lead(db, new.location_id, new.phone, ("booked",))
        if existing is not None:
            _attach(db, existing, new, now)
            return existing, False
        lead_id = _insert_prebooking_lead(db, new, now)
        if lead_id is not None:
            lead = db.get(Lead, lead_id)
            assert lead is not None
            label = _SOURCE_LABELS.get(new.source, new.source)
            _add_activity(
                db,
                lead,
                "system",
                text=f"Lead created via {label}",
                data={"source": new.source},
                author_id=new.author_id,
                now=now,
            )
            log.info(
                "lead_created",
                lead_id=lead.id,
                source=new.source,
                channel=new.channel,
                location_id=new.location_id,
            )
            return lead, True
    raise ValidationFailedError("Could not save the enquiry. Please try again.")


def resolve_lead_token(
    db: Session, token: str | None, *, location_id: int, now: datetime
) -> Lead | None:
    """A token is valid for an open, unlinked lead at the branch, created < 7 days ago."""
    if not token:
        return None
    lead = db.execute(
        select(Lead).where(Lead.lead_token_hash == hash_token(token)).with_for_update()
    ).scalar_one_or_none()
    if (
        lead is None
        or lead.location_id != location_id
        or lead.status not in PREBOOKING_LEAD_STATUSES
        or lead.booking_id is not None
        or lead.created_at < now - LEAD_TOKEN_MAX_AGE
    ):
        return None
    return lead


def _set_token(db: Session, lead: Lead) -> str:
    token = new_lead_token()
    lead.lead_token_hash = hash_token(token)
    db.flush()
    return token


# --- public capture ---------------------------------------------------------


def capture_website_lead(
    db: Session, data: WebsiteLeadIn, *, now: datetime | None = None
) -> str:
    """Booking wizard Step 1 (R2.2, R2.3, R2.7). Returns the raw Lead_Token."""
    now = now or _utcnow()
    _location_or_422(db, data.location_id)
    enquiry = {
        "name": data.name,
        "preferred_date": data.preferred_date,
        "plan_id": _valid_plan_id(db, data.plan_id, data.location_id),
        "start_time": data.start_time,
        "duration_minutes": data.duration_minutes,
        "guests": data.guests,
    }
    lead = resolve_lead_token(db, data.lead_token, location_id=data.location_id, now=now)
    if lead is not None and lead.phone == data.phone:
        # Same browser editing Step 1 again: update details, keep attribution (R17.10).
        for name, value in enquiry.items():
            if value is not None:
                setattr(lead, name, value)
        db.commit()
        assert data.lead_token is not None
        return data.lead_token

    attribution = clean_attribution(data.attribution, own_hosts=_own_hosts())
    new = _NewLead(
        location_id=data.location_id,
        phone=data.phone,
        source="website",
        channel=derive_channel(attribution),
        fields=enquiry,
        attribution=attribution,
        author_id=None,
    )
    lead, _ = _find_or_create_lead(db, new, now=now, attach_to_booked=False)
    token = _set_token(db, lead)
    db.commit()
    return token


def _store_enquiry(
    db: Session,
    *,
    location_id: int,
    phone: str,
    source: str,
    name: str | None,
    preferred_date: date | None,
    message: str | None,
    email: str | None,
    attribution_in: AttributionIn | None,
    extra_note: str | None,
    now: datetime,
) -> None:
    attribution = clean_attribution(attribution_in, own_hosts=_own_hosts())
    new = _NewLead(
        location_id=location_id,
        phone=phone,
        source=source,
        channel=derive_channel(attribution),
        fields={"name": name, "preferred_date": preferred_date, "message": message},
        attribution=attribution,
        author_id=None,
    )
    lead, _ = _find_or_create_lead(db, new, now=now, attach_to_booked=True)
    email_line = f"Email: {email}" if email else None
    parts = [p for p in (message, email_line, extra_note) if p]
    if parts:
        _add_activity(db, lead, "note", text="\n".join(parts)[:TEXT_MAX], now=now)
    db.commit()


def create_enquiry_lead(db: Session, data: EnquiryIn, *, now: datetime | None = None) -> None:
    """Homepage / contact page enquiry (R3.2, R3.3, R3.7)."""
    if data.website:  # honeypot filled -> pretend success, store nothing
        return
    _location_or_422(db, data.location_id)
    _store_enquiry(
        db,
        location_id=data.location_id,
        phone=data.phone,
        source=data.source,
        name=data.name,
        preferred_date=data.preferred_date,
        message=data.message,
        email=data.email,
        attribution_in=data.attribution,
        extra_note=None,
        now=now or _utcnow(),
    )


def create_contact_form_lead(
    db: Session, data: ContactCreate, *, now: datetime | None = None
) -> None:
    """Legacy ``POST /public/contact``: now a ``contact_form`` lead (R3.8).

    Without a usable branch the lead goes to the first active branch with a
    "Branch unknown" note so staff can move it.
    """
    location = db.get(Location, data.location_id) if data.location_id is not None else None
    extra_note = None
    if location is None or not location.is_active:
        location = db.execute(
            select(Location).where(Location.is_active.is_(True)).order_by(Location.id).limit(1)
        ).scalar_one_or_none()
        if location is None:
            raise ValidationFailedError("No branch is accepting enquiries right now.")
        extra_note = "Branch unknown (contact form)"
    _store_enquiry(
        db,
        location_id=location.id,
        phone=data.phone,
        source="contact_form",
        name=data.name,
        preferred_date=None,
        message=data.message,
        email=data.email,
        attribution_in=None,
        extra_note=extra_note,
        now=now or _utcnow(),
    )


def register_enquiry_code(
    db: Session, data: EnquiryCodeIn, *, now: datetime | None = None
) -> None:
    """Store a WhatsApp enquiry code once; later taps only update branch/last seen (R18.5)."""
    now = now or _utcnow()
    location_id = data.location_id
    if location_id is not None:
        location = db.get(Location, location_id)
        if location is None or not location.is_active:
            location_id = None
    attribution = clean_attribution(data.attribution, own_hosts=_own_hosts())
    values: dict[str, Any] = {
        "code": data.code,
        "location_id": location_id,
        "channel": derive_channel(attribution),
        "created_at": now,
        "last_seen_at": now,
    }
    if attribution is not None:
        values.update({name: getattr(attribution, name) for name in _ATTRIBUTION_FIELDS})
    stmt = pg_insert(EnquiryCode).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["code"],
        set_={
            "location_id": stmt.excluded.location_id
            if location_id is not None
            else EnquiryCode.location_id,
            "last_seen_at": now,
        },
    )
    db.execute(stmt)
    db.commit()


# --- admin: create / activities / update ------------------------------------


def _load_lead(db: Session, lead_id: int, actor: CurrentUser, *, lock: bool = False) -> Lead:
    stmt = select(Lead).where(Lead.id == lead_id)
    if lock:
        stmt = stmt.with_for_update()
    lead = db.execute(stmt).scalar_one_or_none()
    if lead is None:
        raise NotFoundError("Lead not found.")
    assert_location_access(actor, lead.location_id)
    return lead


def _apply_enquiry_code(
    db: Session, lead: Lead, code: str, *, author_id: int | None, now: datetime
) -> tuple[str | None, int | None]:
    """Link an enquiry code to a lead (R18.8-R18.11). Returns (warning, other_lead_id)."""
    normalised = code.strip().upper()
    found = db.execute(
        select(EnquiryCode).where(EnquiryCode.code == normalised)
    ).scalar_one_or_none()
    if found is None or found.created_at < now - ENQUIRY_CODE_MAX_AGE:
        return "Unknown or expired enquiry code. The lead was saved without it.", None
    other_id = db.execute(
        select(Lead.id)
        .where(Lead.enquiry_code_id == found.id, Lead.id != lead.id)
        .order_by(Lead.id)
        .limit(1)
    ).scalar_one_or_none()
    lead.enquiry_code_id = found.id
    for name in _ATTRIBUTION_FIELDS:
        setattr(lead, name, getattr(found, name))
    lead.channel = found.channel
    _add_activity(
        db,
        lead,
        "system",
        text=f"Linked enquiry code {normalised}",
        data={"enquiry_code": normalised},
        author_id=author_id,
        now=now,
    )
    return None, other_id


def _set_follow_up(
    db: Session, lead: Lead, when: datetime, *, author_id: int | None, now: datetime
) -> None:
    if lead.status in CLOSED_LEAD_STATUSES:
        raise ValidationFailedError("Reopen the lead before setting a follow-up.")
    lead.follow_up_at = when
    if lead.status in ("new", "contacted"):
        _transition(db, lead, "follow_up", now=now, author_id=author_id)
    _add_activity(
        db,
        lead,
        "follow_up_set",
        data={"follow_up_at": when.isoformat()},
        author_id=author_id,
        now=now,
    )


@dataclass(frozen=True)
class ManualLeadResult:
    lead: Lead
    created: bool
    warning: str | None
    code_used_by_lead_id: int | None


def create_manual_lead(
    db: Session, data: LeadCreate, actor: CurrentUser, *, now: datetime | None = None
) -> ManualLeadResult:
    """Receptionist quick-add (R4.2, R4.3, R4.7, R4.8)."""
    now = now or _utcnow()
    assert_location_access(actor, data.location_id)
    _location_or_422(db, data.location_id)
    new = _NewLead(
        location_id=data.location_id,
        phone=data.phone,
        source=data.source,
        channel=manual_channel(data.source),
        fields={"name": data.name},
        attribution=None,
        author_id=actor.id,
    )
    lead, created = _find_or_create_lead(db, new, now=now, attach_to_booked=True)
    if data.note:
        _add_activity(db, lead, "note", text=data.note, author_id=actor.id, now=now)
    if data.follow_up_at is not None:
        _set_follow_up(db, lead, data.follow_up_at, author_id=actor.id, now=now)
    warning = other = None
    if data.enquiry_code:
        warning, other = _apply_enquiry_code(
            db, lead, data.enquiry_code, author_id=actor.id, now=now
        )
    db.commit()
    db.refresh(lead)
    return ManualLeadResult(lead, created, warning, other)


def add_activity(
    db: Session,
    lead_id: int,
    data: ActivityCreate,
    actor: CurrentUser,
    *,
    now: datetime | None = None,
) -> Lead:
    """Note / call / WhatsApp (R7.2-R7.4). A contact on a `new` lead marks it contacted."""
    now = now or _utcnow()
    lead = _load_lead(db, lead_id, actor, lock=True)
    if data.type in ("call", "whatsapp"):
        if lead.first_contacted_at is None:
            lead.first_contacted_at = now
        if lead.status == "new":
            _transition(db, lead, "contacted", now=now, author_id=actor.id)
    _add_activity(db, lead, data.type, text=data.text, author_id=actor.id, now=now)
    db.commit()
    db.refresh(lead)
    return lead


def _assignable(db: Session, user_id: int, location_id: int) -> bool:
    row = db.execute(
        select(User.is_active, User.location_id, UserRole.name)
        .join(UserRole, User.role_id == UserRole.id)
        .where(User.id == user_id)
    ).one_or_none()
    if row is None or not row.is_active:
        return False
    return row.name == "admin" or row.location_id == location_id


def update_lead(
    db: Session,
    lead_id: int,
    data: LeadUpdate,
    actor: CurrentUser,
    *,
    now: datetime | None = None,
) -> Lead:
    """Name / assignment / status / follow-up from the detail page (R7.5-R7.7, R12.4)."""
    now = now or _utcnow()
    lead = _load_lead(db, lead_id, actor, lock=True)
    changes = data.model_fields_set

    if "name" in changes:
        lead.name = data.name.strip() if data.name and data.name.strip() else None
    if "assigned_user_id" in changes:
        if data.assigned_user_id is not None and not _assignable(
            db, data.assigned_user_id, lead.location_id
        ):
            raise ValidationFailedError("That user cannot be assigned to this branch.")
        lead.assigned_user_id = data.assigned_user_id

    if "status" in changes and data.status is not None and data.status != lead.status:
        if data.status in BOOKING_DRIVEN_STATUSES:
            raise ValidationFailedError("Booked and Won follow the linked booking.")
        if data.status not in MANUAL_STATUS_TARGETS:
            raise ValidationFailedError("Unknown status.")
        if lead.status in BOOKING_DRIVEN_STATUSES:
            raise ValidationFailedError("This lead follows its booking; change the booking.")
        if (
            data.status in CLOSED_LEAD_STATUSES
            and "follow_up_at" in changes
            and data.follow_up_at is not None
        ):
            raise ValidationFailedError("A closed lead cannot have a follow-up.")
        _transition(
            db,
            lead,
            data.status,
            now=now,
            author_id=actor.id,
            reason=data.close_reason,
            reason_text=data.close_reason_text,
        )

    if "follow_up_at" in changes:
        if data.follow_up_at is None:
            lead.follow_up_at = None
        else:
            _set_follow_up(db, lead, data.follow_up_at, author_id=actor.id, now=now)

    db.commit()
    db.refresh(lead)
    return lead


def link_enquiry_code(
    db: Session,
    lead_id: int,
    code: str,
    actor: CurrentUser,
    *,
    now: datetime | None = None,
) -> ManualLeadResult:
    now = now or _utcnow()
    lead = _load_lead(db, lead_id, actor, lock=True)
    warning, other = _apply_enquiry_code(db, lead, code, author_id=actor.id, now=now)
    db.commit()
    db.refresh(lead)
    return ManualLeadResult(lead, False, warning, other)


# --- read model ---------------------------------------------------------------


def is_uncontacted(lead: Lead, now: datetime) -> bool:
    """Uncontacted_New_Lead (R5.8): new, never contacted, older than the alert minutes."""
    return (
        lead.status == "new"
        and lead.first_contacted_at is None
        and lead.created_at
        < now - timedelta(minutes=settings.LEAD_RESPONSE_ALERT_MINUTES)
    )


def to_lead_read(
    db: Session,
    lead: Lead,
    actor: CurrentUser,
    *,
    now: datetime | None = None,
    detail: bool = False,
) -> LeadRead:
    now = now or _utcnow()
    booking_reference = None
    if lead.booking_id is not None:
        booking = db.get(Booking, lead.booking_id)
        booking_reference = booking.booking_reference if booking else None
    plan_title = None
    if lead.plan_id is not None:
        plan = db.get(Plan, lead.plan_id)
        plan_title = plan.title if plan else None
    assigned_name = None
    if lead.assigned_user_id is not None:
        user = db.get(User, lead.assigned_user_id)
        assigned_name = user.username if user else None
    code = db.get(EnquiryCode, lead.enquiry_code_id) if lead.enquiry_code_id else None

    activities: list[ActivityRead] = []
    same_phone: list[LeadBrief] = []
    if detail:
        rows = db.execute(
            select(LeadActivity, User.username)
            .outerjoin(User, LeadActivity.author_user_id == User.id)
            .where(LeadActivity.lead_id == lead.id)
            .order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc())
        ).all()
        activities = [
            ActivityRead(
                id=a.id,
                type=a.type,
                text=a.text,
                data=a.data,
                author_user_id=a.author_user_id,
                author_name=username,
                created_at=a.created_at,
            )
            for a, username in rows
        ]
        others = select(Lead, Location.name).join(
            Location, Lead.location_id == Location.id
        ).where(Lead.phone == lead.phone, Lead.id != lead.id)
        if actor.role != "admin":
            others = others.where(Lead.location_id == actor.location_id)
        same_phone = [
            LeadBrief(
                id=o.id,
                location_id=o.location_id,
                location_name=loc_name,
                status=o.status,
                source=o.source,
                created_at=o.created_at,
            )
            for o, loc_name in db.execute(others.order_by(Lead.created_at.desc())).all()
        ]

    return LeadRead(
        id=lead.id,
        location_id=lead.location_id,
        phone=lead.phone,
        name=lead.name,
        source=lead.source,
        status=lead.status,
        channel=lead.channel,
        close_reason=lead.close_reason,
        close_reason_text=lead.close_reason_text,
        assigned_user_id=lead.assigned_user_id,
        assigned_user_name=assigned_name,
        follow_up_at=lead.follow_up_at,
        last_activity_at=lead.last_activity_at,
        first_contacted_at=lead.first_contacted_at,
        is_uncontacted=is_uncontacted(lead, now),
        minutes_since_created=max(0, int((now - lead.created_at).total_seconds() // 60)),
        booking_id=lead.booking_id,
        booking_reference=booking_reference,
        preferred_date=lead.preferred_date,
        plan_id=lead.plan_id,
        plan_title=plan_title,
        start_time=lead.start_time,
        duration_minutes=lead.duration_minutes,
        guests=lead.guests,
        message=lead.message,
        attribution=AttributionSummary(
            utm_source=lead.utm_source,
            utm_medium=lead.utm_medium,
            utm_campaign=lead.utm_campaign,
            landing_path=lead.landing_path,
            referrer_domain=host_of(lead.referrer),
            has_fbclid=lead.fbclid is not None,
            has_gclid=lead.gclid is not None,
        ),
        enquiry_code=code.code if code else None,
        created_at=lead.created_at,
        activities=activities,
        same_phone_leads=same_phone,
    )


def get_lead(db: Session, lead_id: int, actor: CurrentUser) -> LeadRead:
    lead = _load_lead(db, lead_id, actor)
    return to_lead_read(db, lead, actor, detail=True)


# --- admin API wrappers (routers call exactly one of these) -------------------


def _create_result(db: Session, result: ManualLeadResult, actor: CurrentUser) -> LeadCreateResult:
    return LeadCreateResult(
        lead=to_lead_read(db, result.lead, actor, detail=True),
        created=result.created,
        warning=result.warning,
        code_used_by_lead_id=result.code_used_by_lead_id,
    )


def create_lead_read(db: Session, data: LeadCreate, actor: CurrentUser) -> LeadCreateResult:
    return _create_result(db, create_manual_lead(db, data, actor), actor)


def update_lead_read(
    db: Session, lead_id: int, data: LeadUpdate, actor: CurrentUser
) -> LeadRead:
    return to_lead_read(db, update_lead(db, lead_id, data, actor), actor, detail=True)


def add_activity_read(
    db: Session, lead_id: int, data: ActivityCreate, actor: CurrentUser
) -> LeadRead:
    return to_lead_read(db, add_activity(db, lead_id, data, actor), actor, detail=True)


def link_enquiry_code_read(
    db: Session, lead_id: int, code: str, actor: CurrentUser
) -> LeadCreateResult:
    return _create_result(db, link_enquiry_code(db, lead_id, code, actor), actor)


# --- list, counts, follow-ups (R5, R10, R11) -------------------------------------

_IST = ZoneInfo("Asia/Kolkata")
SEARCH_MIN_CHARS = 3
LAST_NOTE_MAX = 60


def _ist_day_start(day: date) -> datetime:
    """UTC instant of 00:00 IST on ``day``."""
    return datetime.combine(day, time.min, tzinfo=_IST).astimezone(UTC)


def _tomorrow_start(now: datetime) -> datetime:
    return _ist_day_start(now.astimezone(_IST).date() + timedelta(days=1))


def _scope_location(actor: CurrentUser, location_id: int | None) -> int | None:
    """The branch to read: the requested one (checked), else all for admins, else own."""
    if location_id is not None:
        assert_location_access(actor, location_id)
        return location_id
    if actor.role == "admin":
        return None
    if actor.location_id is None:
        raise LocationAccessDeniedError()
    return actor.location_id


def _not_closed() -> ColumnElement[bool]:
    return Lead.status.notin_(CLOSED_LEAD_STATUSES)


def _uncontacted_cond(now: datetime) -> ColumnElement[bool]:
    cutoff = now - timedelta(minutes=settings.LEAD_RESPONSE_ALERT_MINUTES)
    return and_(
        Lead.status == "new",
        Lead.first_contacted_at.is_(None),
        Lead.created_at < cutoff,
    )


def _overdue_cond(now: datetime) -> ColumnElement[bool]:
    return and_(Lead.follow_up_at.is_not(None), Lead.follow_up_at < now, _not_closed())


def _due_today_cond(now: datetime) -> ColumnElement[bool]:
    return and_(
        Lead.follow_up_at >= now,
        Lead.follow_up_at < _tomorrow_start(now),
        _not_closed(),
    )


@dataclass(frozen=True)
class LeadListFilters:
    location_id: int | None = None
    statuses: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    assigned_user_id: int | None = None
    follow_from: date | None = None
    follow_to: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    q: str | None = None
    limit: int = 50
    offset: int = 0


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _list_conditions(f: LeadListFilters, location_id: int | None) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = []
    if location_id is not None:
        conds.append(Lead.location_id == location_id)
    if f.statuses:
        conds.append(Lead.status.in_(f.statuses))
    if f.sources:
        conds.append(Lead.source.in_(f.sources))
    if f.channels:
        conds.append(Lead.channel.in_(f.channels))
    if f.assigned_user_id is not None:
        conds.append(Lead.assigned_user_id == f.assigned_user_id)
    if f.follow_from is not None:
        conds.append(Lead.follow_up_at >= _ist_day_start(f.follow_from))
    if f.follow_to is not None:
        conds.append(Lead.follow_up_at < _ist_day_start(f.follow_to + timedelta(days=1)))
    if f.created_from is not None:
        conds.append(Lead.created_at >= _ist_day_start(f.created_from))
    if f.created_to is not None:
        conds.append(Lead.created_at < _ist_day_start(f.created_to + timedelta(days=1)))
    if f.q:
        text_q = f.q.strip()
        if len(text_q) < SEARCH_MIN_CHARS:
            raise ValidationFailedError("Search needs at least 3 characters.")
        name_match = Lead.name.ilike(f"%{_escape_like(text_q)}%", escape="\\")
        digits = re.sub(r"\D", "", text_q)
        if len(digits) >= SEARCH_MIN_CHARS:
            conds.append(or_(name_match, Lead.phone.like(f"%{digits}%")))
        else:
            conds.append(name_match)
    return conds


def _section(now: datetime) -> ColumnElement[int]:
    """R5.1/R5.8 sections: 1 uncontacted, 2 overdue, 3 due today, 4 new, 5 other."""
    return case(
        (_uncontacted_cond(now), 1),
        (_overdue_cond(now), 2),
        (_due_today_cond(now), 3),
        (and_(Lead.status == "new", Lead.follow_up_at.is_(None)), 4),
        else_=5,
    )


def _section_key(section: ColumnElement[int]) -> ColumnElement[Any]:
    """Within a section: oldest uncontacted, earliest follow-up, newest new, latest activity."""
    return case(
        (section == 1, extract("epoch", Lead.created_at)),
        (section.in_((2, 3)), extract("epoch", Lead.follow_up_at)),
        (section == 4, -extract("epoch", Lead.created_at)),
        else_=-extract("epoch", Lead.last_activity_at),
    )


def list_leads(
    db: Session,
    actor: CurrentUser,
    filters: LeadListFilters,
    *,
    now: datetime | None = None,
) -> LeadListPage:
    """Leads page (R5.1-R5.4, R5.8): section ordering, then key time, then id."""
    now = now or _utcnow()
    location_id = _scope_location(actor, filters.location_id)
    conds = _list_conditions(filters, location_id)
    total = db.execute(select(func.count()).select_from(Lead).where(*conds)).scalar_one()
    section = _section(now)
    rows = db.execute(
        select(Lead)
        .where(*conds)
        .order_by(section, _section_key(section), Lead.id.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    ).scalars()
    return LeadListPage(
        items=[to_lead_read(db, lead, actor, now=now) for lead in rows],
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


def lead_counts(
    db: Session,
    actor: CurrentUser,
    location_id: int | None,
    *,
    now: datetime | None = None,
) -> LeadCounts:
    """Badge counts in one query (R5.9, R10.1, R10.2)."""
    now = now or _utcnow()
    scoped = _scope_location(actor, location_id)
    stmt = select(
        func.count().filter(_uncontacted_cond(now)),
        func.count().filter(_overdue_cond(now)),
        func.count().filter(_due_today_cond(now)),
    ).select_from(Lead)
    if scoped is not None:
        stmt = stmt.where(Lead.location_id == scoped)
    uncontacted, overdue, due_today = db.execute(stmt).one()
    return LeadCounts(uncontacted=uncontacted, overdue=overdue, due_today=due_today)


def follow_up_digest(
    db: Session,
    actor: CurrentUser,
    location_id: int | None,
    *,
    now: datetime | None = None,
) -> FollowUpDigest:
    """Overdue + due-today leads for the branch WhatsApp message (R11.2)."""
    now = now or _utcnow()
    scoped = _scope_location(actor, location_id)
    last_note = (
        select(LeadActivity.text)
        .where(
            LeadActivity.lead_id == Lead.id,
            LeadActivity.type == "note",
            LeadActivity.text.is_not(None),
        )
        .order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc())
        .limit(1)
        .correlate(Lead)
        .scalar_subquery()
    )
    stmt = (
        select(Lead, last_note)
        .where(or_(_overdue_cond(now), _due_today_cond(now)))
        .order_by(Lead.follow_up_at, Lead.id)
    )
    if scoped is not None:
        stmt = stmt.where(Lead.location_id == scoped)
    items = []
    for lead, note in db.execute(stmt).all():
        assert lead.follow_up_at is not None
        items.append(
            FollowUpItem(
                id=lead.id,
                name=lead.name,
                phone=lead.phone,
                status=lead.status,
                follow_up_at=lead.follow_up_at,
                is_overdue=lead.follow_up_at < now,
                last_note=note[:LAST_NOTE_MAX] if note else None,
            )
        )
    return FollowUpDigest(items=items)


def assignable_users(
    db: Session, actor: CurrentUser, location_id: int
) -> list[AssignableUser]:
    """Active users who may work this branch: its staff plus all admins (R12.4)."""
    assert_location_access(actor, location_id)
    rows = db.execute(
        select(User.id, User.username, UserRole.name)
        .join(UserRole, User.role_id == UserRole.id)
        .where(
            User.is_active.is_(True),
            or_(UserRole.name == "admin", User.location_id == location_id),
        )
        .order_by(User.username)
    ).all()
    return [AssignableUser(id=r.id, username=r.username, role=r.name) for r in rows]


# --- dashboard (R13, admin only) --------------------------------------------------

DASHBOARD_MAX_DAYS = 366


def dashboard(
    db: Session,
    actor: CurrentUser,
    *,
    location_id: int | None,
    date_from: date,
    date_to: date,
) -> LeadDashboard:
    """All figures in aggregate SQL over leads created in the IST date range."""
    if actor.role != "admin":
        raise ForbiddenError()
    if date_to < date_from:
        raise ValidationFailedError("date_to must be on or after date_from.")
    if (date_to - date_from).days >= DASHBOARD_MAX_DAYS:
        raise ValidationFailedError("Choose a range of at most one year.")
    conds: list[ColumnElement[bool]] = [
        Lead.created_at >= _ist_day_start(date_from),
        Lead.created_at < _ist_day_start(date_to + timedelta(days=1)),
    ]
    if location_id is not None:
        conds.append(Lead.location_id == location_id)
    won = func.count().filter(Lead.status == "won")
    day = cast(func.timezone("Asia/Kolkata", Lead.created_at), Date)

    def per_day(column: Any) -> list[DashboardDayRow]:
        rows = db.execute(
            select(day, column, func.count())
            .where(*conds)
            .group_by(day, column)
            .order_by(day, column)
        ).all()
        return [DashboardDayRow(day=d, key=k, count=c) for d, k, c in rows]

    def grouped(column: Any, *extra: ColumnElement[bool]) -> list[DashboardGroupRow]:
        rows = db.execute(
            select(column, func.count(), won)
            .where(*conds, *extra)
            .group_by(column)
            .order_by(func.count().desc(), column)
        ).all()
        return [DashboardGroupRow(key=k, total=t, won=w) for k, t, w in rows]

    total, won_total = db.execute(select(func.count(), won).where(*conds)).one()

    seconds = extract("epoch", Lead.first_contacted_at - Lead.created_at)
    contacted, avg_s, median_s = db.execute(
        select(
            func.count(),
            func.avg(seconds),
            func.percentile_cont(0.5).within_group(seconds),
        ).where(*conds, Lead.first_contacted_at.is_not(None))
    ).one()

    reasons = db.execute(
        select(Lead.close_reason, func.count())
        .where(
            *conds,
            Lead.status.in_(("lost", "not_interested")),
            Lead.close_reason.is_not(None),
        )
        .group_by(Lead.close_reason)
        .order_by(func.count().desc(), Lead.close_reason)
    ).all()

    wa_total, wa_coded = db.execute(
        select(func.count(), func.count().filter(Lead.enquiry_code_id.is_not(None))).where(
            *conds, Lead.source.in_(("whatsapp", "whatsapp_ad"))
        )
    ).one()

    def _minutes(value: Any) -> int | None:
        return None if value is None else int(round(float(value) / 60))

    return LeadDashboard(
        location_id=location_id,
        date_from=date_from,
        date_to=date_to,
        total=total,
        won=won_total,
        per_day_by_source=per_day(Lead.source),
        per_day_by_channel=per_day(Lead.channel),
        by_source=grouped(Lead.source),
        by_channel=grouped(Lead.channel),
        contacted=contacted,
        avg_first_response_minutes=_minutes(avg_s),
        median_first_response_minutes=_minutes(median_s),
        close_reasons=[DashboardReasonRow(reason=r, count=c) for r, c in reasons],
        campaigns=grouped(Lead.utm_campaign, Lead.utm_campaign.is_not(None)),
        whatsapp_total=wa_total,
        whatsapp_with_code=wa_coded,
    )


# --- auto-close job (R14) -----------------------------------------------------------


def close_stale_leads(db: Session, *, now: datetime, days: int) -> int:
    """Close untouched open leads as ``lost`` / ``no_response``. Returns the count.

    ``days == 0`` (the default) means never: nothing is queried or changed (R14.7).
    ``booked`` leads and leads with a future follow-up stay open (R14.2, R14.3).
    Each close writes activities, which refresh ``last_activity_at``, so an
    immediate second run finds nothing (R14.5). One commit for the batch.
    """
    if days <= 0:
        return 0
    stale = db.execute(
        select(Lead)
        .where(
            Lead.status.in_(PREBOOKING_LEAD_STATUSES),
            Lead.last_activity_at < now - timedelta(days=days),
            or_(Lead.follow_up_at.is_(None), Lead.follow_up_at < now),
        )
        .order_by(Lead.id)
        .with_for_update(skip_locked=True)
    ).scalars().all()
    note_text = f"Closed automatically after {days} days without activity"
    for lead in stale:
        _transition(db, lead, "lost", now=now, reason="no_response")
        _add_activity(
            db, lead, "system", text=note_text, data={"auto_close_days": days}, now=now
        )
    db.commit()
    return len(stale)


# --- booking hooks (lead follows its booking, R2.9-R2.11, R8, R9.3) -----------
#
# Called from services/booking.py inside the booking's own transaction, right
# before it commits. Each hook runs in a SAVEPOINT: if anything goes wrong only
# the lead change is rolled back, an error code is logged, and the booking
# operation commits exactly as it would without leads (R16.1).

_OUTCOME_WORDS = {
    "rejected": "was rejected",
    "expired": "expired",
    "cancelled": "was cancelled",
}


@contextmanager
def _lead_savepoint(db: Session, code: str, booking_id: int | None) -> Iterator[None]:
    savepoint = db.begin_nested()
    try:
        yield
        savepoint.commit()
    except Exception:  # noqa: BLE001 - lead work must never break a booking
        savepoint.rollback()
        log.error("lead_hook_failed", code=code, booking_id=booking_id)


def _booking_enquiry_fields(booking: Booking) -> dict[str, Any]:
    return {
        "name": (booking.booking_name or "").strip()[:120] or None,
        "preferred_date": booking.booking_date,
        "plan_id": booking.plan_id,
        "start_time": booking.start_time,
        "duration_minutes": booking.duration_minutes,
        "guests": (booking.people or 0) + (booking.kids or 0) or None,
    }


def _link(
    db: Session,
    lead: Lead,
    booking: Booking,
    *,
    author_id: int | None,
    now: datetime,
) -> None:
    for name, value in _booking_enquiry_fields(booking).items():
        if value is not None:
            setattr(lead, name, value)
    lead.booking_id = booking.id
    db.flush()
    target = "won" if booking.status == "accepted" else "booked"
    _transition(
        db,
        lead,
        target,
        now=now,
        author_id=None,  # status follows the booking; not a manual contact
        note=f"Booking {booking.booking_reference}",
    )
    _add_activity(
        db,
        lead,
        "booking_linked",
        text=f"Booking {booking.booking_reference} created",
        data={"booking_reference": booking.booking_reference},
        author_id=author_id,
        now=now,
    )


def _apply_public_link(
    db: Session, booking: Booking, lead_token: str | None, now: datetime
) -> None:
    phone = normalize_indian_mobile(booking.phone or "")
    if phone is None:
        return
    lead = resolve_lead_token(db, lead_token, location_id=booking.location_id, now=now)
    if lead is not None and lead.phone != phone:
        lead = None
    if lead is None:
        new = _NewLead(
            location_id=booking.location_id,
            phone=phone,
            source="website",
            channel="direct",
            fields=_booking_enquiry_fields(booking),
            attribution=None,
            author_id=None,
        )
        lead, _ = _find_or_create_lead(db, new, now=now, attach_to_booked=False)
    _link(db, lead, booking, author_id=None, now=now)


def link_public_booking(db: Session, booking: Booking, lead_token: str | None) -> None:
    """Link a new customer booking to its lead (by token, else by phone). R2.9, R2.10."""
    with _lead_savepoint(db, "link_public_booking", booking.id):
        _apply_public_link(db, booking, lead_token, _utcnow())


def validate_admin_lead(
    db: Session, lead_id: int, location_id: int, actor: CurrentUser
) -> None:
    """Checked before an admin booking is created from a lead (422 on any problem)."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise ValidationFailedError("The lead does not exist.")
    assert_location_access(actor, lead.location_id)
    if lead.location_id != location_id:
        raise ValidationFailedError("The lead belongs to another branch.")
    if lead.status not in PREBOOKING_LEAD_STATUSES:
        raise ValidationFailedError("This lead is already booked or closed.")


def link_admin_booking(
    db: Session, booking: Booking, lead_id: int, actor: CurrentUser
) -> None:
    """Link a booking created from a lead in the admin panel (R9.3)."""
    with _lead_savepoint(db, "link_admin_booking", booking.id):
        lead = db.execute(
            select(Lead).where(Lead.id == lead_id).with_for_update()
        ).scalar_one()
        _link(db, lead, booking, author_id=actor.id, now=_utcnow())


def _apply_status_change(db: Session, booking: Booking, new_status: str, now: datetime) -> None:
    lead = db.execute(
        select(Lead).where(Lead.booking_id == booking.id).with_for_update()
    ).scalar_one_or_none()
    if lead is None:
        return
    ref = booking.booking_reference
    if new_status == "accepted":
        _transition(db, lead, "won", now=now, note=f"Booking {ref} accepted")
        return
    if new_status == "pending":  # reinstated (expired -> pending)
        if lead.status == "follow_up":
            _transition(db, lead, "booked", now=now, note=f"Booking {ref} reinstated")
        return
    outcome = _OUTCOME_WORDS.get(new_status)
    if outcome is None or lead.status not in ("booked", "won"):
        return
    other = db.execute(
        select(Lead.id).where(
            Lead.location_id == lead.location_id,
            Lead.phone == lead.phone,
            Lead.id != lead.id,
            Lead.status.in_(PREBOOKING_LEAD_STATUSES),
        )
    ).scalar_one_or_none()
    if other is not None:
        # The customer already has another open enquiry; keep work on that one.
        _transition(
            db,
            lead,
            "lost",
            now=now,
            reason="other",
            reason_text="Customer has another open enquiry",
            note=f"Booking {ref} {outcome}",
        )
        other_lead = db.get(Lead, other)
        assert other_lead is not None
        _add_activity(
            db,
            other_lead,
            "system",
            text=f"Earlier booking {ref} {outcome}",
            data={"booking_reference": ref},
            now=now,
        )
        return
    _transition(db, lead, "follow_up", now=now, note=f"Booking {ref} {outcome}")
    lead.follow_up_at = now
    _add_activity(
        db,
        lead,
        "system",
        text=f"Booking {ref} {outcome}. Follow up with the customer.",
        data={"booking_reference": ref, "booking_status": new_status},
        now=now,
    )


def on_booking_status_changed(db: Session, booking: Booking, new_status: str) -> None:
    """Move the linked lead with its booking (R8.1-R8.7). No-op without a linked lead."""
    with _lead_savepoint(db, "booking_status_changed", booking.id):
        _apply_status_change(db, booking, new_status, _utcnow())
