"""Lead CRM models: leads, their activity timeline, and WhatsApp enquiry codes.

A Lead is one enquiry from one customer (phone) at one branch. It is separate
from bookings: a lead may link to a booking, but bookings never depend on leads
and no booking status or rule changes because of this feature.

Business rules (status transitions, duplicates, Channel) live in
``services/leads.py``; this module only declares tables, constraints and indexes.
"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin

LEAD_STATUSES = (
    "new",
    "contacted",
    "follow_up",
    "booked",
    "won",
    "not_interested",
    "lost",
)
# Statuses that count as an Open_Lead (shown in work lists, eligible for attach).
OPEN_LEAD_STATUSES = ("new", "contacted", "follow_up", "booked")
# Open statuses before a booking exists: at most one per (branch, phone).
PREBOOKING_LEAD_STATUSES = ("new", "contacted", "follow_up")
CLOSED_LEAD_STATUSES = ("won", "not_interested", "lost")

LEAD_SOURCES = (
    "website",
    "homepage_form",
    "contact_form",
    "whatsapp",
    "whatsapp_ad",
    "phone",
    "walk_in",
    "instagram_dm",
    "other",
    "instant_form",  # reserved for the later Lead Ads spec
)
# Sources a receptionist may pick in quick-add.
MANUAL_LEAD_SOURCES = (
    "whatsapp",
    "whatsapp_ad",
    "phone",
    "walk_in",
    "instagram_dm",
    "other",
)

LEAD_CHANNELS = (
    "meta_ads",
    "google_ads",
    "google_business_profile",
    "google_search",
    "instagram_organic",
    "facebook_organic",
    "other_referral",
    "direct",
    "manual",
)

CLOSE_REASONS = (
    "price_budget",
    "date_not_available",
    "booked_elsewhere",
    "no_response",
    "just_enquiring",
    "other",
)

ACTIVITY_TYPES = (
    "note",
    "call",
    "whatsapp",
    "status_change",
    "follow_up_set",
    "booking_linked",
    "system",
)

# Length limits (A8, R1.4, design data model).
NAME_MAX = 120
TEXT_MAX = 2000
CLOSE_REASON_TEXT_MAX = 500
UTM_MAX = 200
URLISH_MAX = 500

# Enquiry code alphabet: no 0/O, 1/I/L (A14).
ENQUIRY_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ENQUIRY_CODE_PATTERN = f"^[{ENQUIRY_CODE_ALPHABET}]{{6}}$"


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class EnquiryCode(Base):
    """A short code put in website WhatsApp messages, with the visitor's attribution.

    Holds no name, phone or message text (R18.6).
    """

    __tablename__ = "enquiry_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    utm_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    fbclid: Mapped[str | None] = mapped_column(Text, nullable=True)
    gclid: Mapped[str | None] = mapped_column(Text, nullable=True)
    landing_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
    landed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("uq_enquiry_codes_code", "code", unique=True),
        CheckConstraint(
            f"code ~ '{ENQUIRY_CODE_PATTERN}'", name="ck_enquiry_codes_code_format"
        ),
        CheckConstraint(_in("channel", LEAD_CHANNELS), name="ck_enquiry_codes_channel"),
    )


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    # 10-digit Indian mobile, digits only (A2).
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'new'")
    )
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'direct'")
    )
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    first_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True
    )
    # SHA-256 hex of the Lead_Token; the raw token is never stored.
    lead_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Enquiry details (all optional).
    preferred_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    guests: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Landing attribution (R17); query strings stripped before storage.
    utm_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    utm_term: Mapped[str | None] = mapped_column(Text, nullable=True)
    fbclid: Mapped[str | None] = mapped_column(Text, nullable=True)
    gclid: Mapped[str | None] = mapped_column(Text, nullable=True)
    landing_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer: Mapped[str | None] = mapped_column(Text, nullable=True)
    landed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enquiry_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("enquiry_codes.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("phone ~ '^[6-9][0-9]{9}$'", name="ck_leads_phone_digits"),
        CheckConstraint(
            f"name IS NULL OR char_length(name) <= {NAME_MAX}", name="ck_leads_name_len"
        ),
        CheckConstraint(_in("source", LEAD_SOURCES), name="ck_leads_source"),
        CheckConstraint(_in("status", LEAD_STATUSES), name="ck_leads_status"),
        CheckConstraint(
            "close_reason IS NULL OR " + _in("close_reason", CLOSE_REASONS),
            name="ck_leads_close_reason",
        ),
        CheckConstraint(
            "close_reason_text IS NULL OR "
            f"char_length(close_reason_text) <= {CLOSE_REASON_TEXT_MAX}",
            name="ck_leads_close_reason_text_len",
        ),
        CheckConstraint(_in("channel", LEAD_CHANNELS), name="ck_leads_channel"),
        CheckConstraint("guests IS NULL OR guests >= 1", name="ck_leads_guests_positive"),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 1",
            name="ck_leads_duration_positive",
        ),
        CheckConstraint(
            f"message IS NULL OR char_length(message) <= {TEXT_MAX}",
            name="ck_leads_message_len",
        ),
        # R1.8: a lost / not-interested lead always carries a reason.
        CheckConstraint(
            "status NOT IN ('lost', 'not_interested') OR close_reason IS NOT NULL",
            name="ck_leads_closed_has_reason",
        ),
        # R1.9: closed leads have no pending follow-up.
        CheckConstraint(
            "status NOT IN ('won', 'lost', 'not_interested') OR follow_up_at IS NULL",
            name="ck_leads_closed_no_follow_up",
        ),
        Index("uq_leads_booking_id", "booking_id", unique=True),
        Index("uq_leads_lead_token_hash", "lead_token_hash", unique=True),
        # R6.4: at most one pre-booking open lead per (branch, phone), race-safe.
        Index(
            "uq_leads_prebooking_phone",
            "location_id",
            "phone",
            unique=True,
            postgresql_where=text(
                "status IN ('new', 'contacted', 'follow_up')"
            ),
        ),
        Index("ix_leads_location_status", "location_id", "status"),
        Index("ix_leads_location_follow_up", "location_id", "follow_up_at"),
        Index("ix_leads_location_created", "location_id", "created_at"),
        Index("ix_leads_phone", "phone"),
    )


class LeadActivity(Base):
    """Append-only timeline entry on a Lead (never updated or deleted)."""

    __tablename__ = "lead_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured detail, e.g. {"from": "new", "to": "contacted"}.
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # NULL = customer or system action.
    author_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(_in("type", ACTIVITY_TYPES), name="ck_lead_activities_type"),
        CheckConstraint(
            f"text IS NULL OR char_length(text) <= {TEXT_MAX}",
            name="ck_lead_activities_text_len",
        ),
        Index("ix_lead_activities_lead_created", "lead_id", "created_at"),
    )
