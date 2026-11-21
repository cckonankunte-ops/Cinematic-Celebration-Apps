"""create_leads_crm

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-22 00:00:00

Lead CRM (feature: lead-crm).

- ``enquiry_codes``: website WhatsApp enquiry codes with landing attribution
  (no name/phone/message).
- ``leads``: one enquiry per customer phone per branch, optional link to a
  booking, attribution + Channel. A partial unique index allows at most one
  pre-booking open lead (new/contacted/follow_up) per (branch, phone).
- ``lead_activities``: append-only timeline per lead.
- ``locations.whatsapp_phone``: optional branch WhatsApp number.
- Copies legacy ``contact_leads`` rows into ``leads`` (``contact_leads`` itself is
  left untouched, read-only, for rollback).

Bookings are not changed: no new booking status, no booking column.

``downgrade()`` drops the three tables (activities, leads, codes) and the column.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_log = logging.getLogger("alembic.runtime.migration")

_STATUSES = ("new", "contacted", "follow_up", "booked", "won", "not_interested", "lost")
_SOURCES = (
    "website", "homepage_form", "contact_form", "whatsapp", "whatsapp_ad", "phone",
    "walk_in", "instagram_dm", "other", "instant_form",
)
_CHANNELS = (
    "meta_ads", "google_ads", "google_business_profile", "google_search",
    "instagram_organic", "facebook_organic", "other_referral", "direct", "manual",
)
_REASONS = (
    "price_budget", "date_not_available", "booked_elsewhere", "no_response",
    "just_enquiring", "other",
)
_ACTIVITY_TYPES = (
    "note", "call", "whatsapp", "status_change", "follow_up_set", "booking_linked",
    "system",
)
_CODE_PATTERN = "^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _attribution_columns() -> list[sa.Column]:
    return [
        sa.Column("utm_source", sa.Text(), nullable=True),
        sa.Column("utm_medium", sa.Text(), nullable=True),
        sa.Column("utm_campaign", sa.Text(), nullable=True),
        sa.Column("utm_content", sa.Text(), nullable=True),
        sa.Column("utm_term", sa.Text(), nullable=True),
        sa.Column("fbclid", sa.Text(), nullable=True),
        sa.Column("gclid", sa.Text(), nullable=True),
        sa.Column("landing_path", sa.Text(), nullable=True),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.Column("landed_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _now() -> sa.TextClause:
    return sa.text("now()")


def _ts(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column:
    """A timestamptz column, NOT NULL default now() unless told otherwise."""
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=_now() if default else None,
    )


def upgrade() -> None:
    op.add_column("locations", sa.Column("whatsapp_phone", sa.Text(), nullable=True))

    op.create_table(
        "enquiry_codes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        *_attribution_columns(),
        _ts("created_at"),
        _ts("last_seen_at"),
        sa.PrimaryKeyConstraint("id", name="pk_enquiry_codes"),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"],
            name="fk_enquiry_codes_location_id", ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            f"code ~ '{_CODE_PATTERN}'", name="ck_enquiry_codes_code_format"
        ),
        sa.CheckConstraint(_in("channel", _CHANNELS), name="ck_enquiry_codes_channel"),
    )
    op.create_index("uq_enquiry_codes_code", "enquiry_codes", ["code"], unique=True)

    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default=sa.text("'new'")
        ),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("close_reason_text", sa.Text(), nullable=True),
        sa.Column(
            "channel", sa.Text(), nullable=False, server_default=sa.text("'direct'")
        ),
        sa.Column("assigned_user_id", sa.BigInteger(), nullable=True),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        _ts("last_activity_at"),
        sa.Column("first_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("booking_id", sa.BigInteger(), nullable=True),
        sa.Column("lead_token_hash", sa.Text(), nullable=True),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("plan_id", sa.BigInteger(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("duration_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("guests", sa.SmallInteger(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        *_attribution_columns(),
        sa.Column("enquiry_code_id", sa.BigInteger(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name="pk_leads"),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"],
            name="fk_leads_location_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_user_id"], ["users.id"],
            name="fk_leads_assigned_user_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"],
            name="fk_leads_booking_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name="fk_leads_plan_id", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["enquiry_code_id"], ["enquiry_codes.id"],
            name="fk_leads_enquiry_code_id", ondelete="SET NULL",
        ),
        sa.CheckConstraint("phone ~ '^[6-9][0-9]{9}$'", name="ck_leads_phone_digits"),
        sa.CheckConstraint(
            "name IS NULL OR char_length(name) <= 120", name="ck_leads_name_len"
        ),
        sa.CheckConstraint(_in("source", _SOURCES), name="ck_leads_source"),
        sa.CheckConstraint(_in("status", _STATUSES), name="ck_leads_status"),
        sa.CheckConstraint(
            "close_reason IS NULL OR " + _in("close_reason", _REASONS),
            name="ck_leads_close_reason",
        ),
        sa.CheckConstraint(
            "close_reason_text IS NULL OR char_length(close_reason_text) <= 500",
            name="ck_leads_close_reason_text_len",
        ),
        sa.CheckConstraint(_in("channel", _CHANNELS), name="ck_leads_channel"),
        sa.CheckConstraint(
            "guests IS NULL OR guests >= 1", name="ck_leads_guests_positive"
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 1",
            name="ck_leads_duration_positive",
        ),
        sa.CheckConstraint(
            "message IS NULL OR char_length(message) <= 2000", name="ck_leads_message_len"
        ),
        sa.CheckConstraint(
            "status NOT IN ('lost', 'not_interested') OR close_reason IS NOT NULL",
            name="ck_leads_closed_has_reason",
        ),
        sa.CheckConstraint(
            "status NOT IN ('won', 'lost', 'not_interested') OR follow_up_at IS NULL",
            name="ck_leads_closed_no_follow_up",
        ),
    )
    op.create_index("uq_leads_booking_id", "leads", ["booking_id"], unique=True)
    op.create_index("uq_leads_lead_token_hash", "leads", ["lead_token_hash"], unique=True)
    op.create_index(
        "uq_leads_prebooking_phone",
        "leads",
        ["location_id", "phone"],
        unique=True,
        postgresql_where=sa.text("status IN ('new', 'contacted', 'follow_up')"),
    )
    op.create_index("ix_leads_location_status", "leads", ["location_id", "status"])
    op.create_index("ix_leads_location_follow_up", "leads", ["location_id", "follow_up_at"])
    op.create_index("ix_leads_location_created", "leads", ["location_id", "created_at"])
    op.create_index("ix_leads_phone", "leads", ["phone"])

    op.create_table(
        "lead_activities",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id", name="pk_lead_activities"),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"],
            name="fk_lead_activities_lead_id", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"],
            name="fk_lead_activities_author_user_id", ondelete="SET NULL",
        ),
        sa.CheckConstraint(_in("type", _ACTIVITY_TYPES), name="ck_lead_activities_type"),
        sa.CheckConstraint(
            "text IS NULL OR char_length(text) <= 2000", name="ck_lead_activities_text_len"
        ),
    )
    op.create_index(
        "ix_lead_activities_lead_created", "lead_activities", ["lead_id", "created_at"]
    )

    # Copy legacy contact-form messages into leads (contact_leads is untouched).
    from app.services.lead_migration import copy_contact_leads

    result = copy_contact_leads(op.get_bind())
    _log.info(
        "contact_leads copied=%s attached=%s skipped_invalid_phone=%s",
        result.copied,
        result.attached,
        result.skipped,
    )


def downgrade() -> None:
    op.drop_index("ix_lead_activities_lead_created", table_name="lead_activities")
    op.drop_table("lead_activities")
    for name in (
        "ix_leads_phone",
        "ix_leads_location_created",
        "ix_leads_location_follow_up",
        "ix_leads_location_status",
        "uq_leads_prebooking_phone",
        "uq_leads_lead_token_hash",
        "uq_leads_booking_id",
    ):
        op.drop_index(name, table_name="leads")
    op.drop_table("leads")
    op.drop_index("uq_enquiry_codes_code", table_name="enquiry_codes")
    op.drop_table("enquiry_codes")
    op.drop_column("locations", "whatsapp_phone")
