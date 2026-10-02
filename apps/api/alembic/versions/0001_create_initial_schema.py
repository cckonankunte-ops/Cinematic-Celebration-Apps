"""create_initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00

Creates the full Phase 1 schema: catalog + users, bookings with the
booking_status enum and the uq_bookings_active_slot partial unique index,
booking_items, payments, booking_events, and contact_leads. All money is
bigint paise; all foreign keys are explicit; CHECK constraints are declared
at the DB level.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )

    op.create_table(
        "locations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "role_id",
            sa.BigInteger(),
            sa.ForeignKey("user_roles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.BigInteger(),
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "plans",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "location_id",
            sa.BigInteger(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("plan_type", sa.Integer(), nullable=False),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column("people_allowed", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("max_people_allowed", sa.Integer(), nullable=False),
        sa.Column("extra_guest_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("give_discount", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_discount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("advance_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "effective_to", sa.Date(), nullable=False, server_default=sa.text("'2099-12-31'")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_plans_location_id", "plans", ["location_id"])

    op.create_table(
        "plan_gallery_images",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "plan_id",
            sa.BigInteger(),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_plan_gallery_plan_id", "plan_gallery_images", ["plan_id"])

    op.create_table(
        "slots",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "plan_id",
            sa.BigInteger(),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("show_combos", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "effective_to", sa.Date(), nullable=False, server_default=sa.text("'2099-12-31'")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_slots_plan_id", "slots", ["plan_id"])

    op.create_table(
        "occasions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "location_id",
            sa.BigInteger(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_occasions_location_id", "occasions", ["location_id"])

    op.create_table(
        "cakes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "location_id",
            sa.BigInteger(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "effective_to", sa.Date(), nullable=False, server_default=sa.text("'2199-12-31'")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_cakes_location_id", "cakes", ["location_id"])

    op.create_table(
        "special_decor_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "location_id",
            sa.BigInteger(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "effective_to", sa.Date(), nullable=False, server_default=sa.text("'2099-12-31'")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_special_decor_location_id", "special_decor_items", ["location_id"])

    op.create_table(
        "combo_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "location_id",
            sa.BigInteger(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "effective_to", sa.Date(), nullable=False, server_default=sa.text("'2099-12-31'")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_combo_items_location_id", "combo_items", ["location_id"])

    booking_status = postgresql.ENUM(
        "pending", "accepted", "rejected", "expired", name="booking_status"
    )
    booking_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "bookings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("booking_reference", sa.String(), nullable=False, unique=True),
        sa.Column("public_token", sa.String(), nullable=False, unique=True),
        sa.Column(
            "location_id",
            sa.BigInteger(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.BigInteger(),
            sa.ForeignKey("plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "slot_id",
            sa.BigInteger(),
            sa.ForeignKey("slots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("booking_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("special_person_name", sa.String(), nullable=True),
        sa.Column("name_on_cake", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("people", sa.Integer(), nullable=False),
        sa.Column(
            "occasion_id",
            sa.BigInteger(),
            sa.ForeignKey("occasions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("plan_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("extra_guest_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("subtotal_paise", sa.BigInteger(), nullable=False),
        sa.Column("discount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("food_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("other_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cleaning_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_paise", sa.BigInteger(), nullable=False),
        sa.Column("advance_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM(name="booking_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("confirmation_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "crm_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_bookings_location_id", "bookings", ["location_id"])
    op.create_index("ix_bookings_booking_date", "bookings", ["booking_date"])
    op.create_index("ix_bookings_status", "bookings", ["status"])
    op.create_index("ix_bookings_created_at", "bookings", ["created_at"])
    # Double-booking prevention: one active booking per (location, slot, date).
    op.create_index(
        "uq_bookings_active_slot",
        "bookings",
        ["location_id", "slot_id", "booking_date"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'accepted')"),
    )

    op.create_table(
        "booking_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "booking_id",
            sa.BigInteger(),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=True),
        sa.Column("name_snapshot", sa.Text(), nullable=False),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("kind IN ('cake','decor','combo')", name="ck_booking_items_kind"),
    )
    op.create_index("ix_booking_items_booking_id", "booking_items", ["booking_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "booking_id",
            sa.BigInteger(),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "recorded_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("provider_ref", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount_paise > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint("method IN ('cash','upi','card','other')", name="ck_payments_method"),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])

    op.create_table(
        "booking_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "booking_id",
            sa.BigInteger(),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "event_type IN ('created','accepted','rejected','edited','payment_recorded','expired')",
            name="ck_booking_events_type",
        ),
    )
    op.create_index("ix_booking_events_booking_id", "booking_events", ["booking_id"])

    op.create_table(
        "contact_leads",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("contact_leads")
    op.drop_index("ix_booking_events_booking_id", table_name="booking_events")
    op.drop_table("booking_events")
    op.drop_index("ix_payments_booking_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_booking_items_booking_id", table_name="booking_items")
    op.drop_table("booking_items")
    op.drop_index("uq_bookings_active_slot", table_name="bookings")
    op.drop_index("ix_bookings_created_at", table_name="bookings")
    op.drop_index("ix_bookings_status", table_name="bookings")
    op.drop_index("ix_bookings_booking_date", table_name="bookings")
    op.drop_index("ix_bookings_location_id", table_name="bookings")
    op.drop_table("bookings")
    op.execute("DROP TYPE IF EXISTS booking_status")
    op.drop_index("ix_combo_items_location_id", table_name="combo_items")
    op.drop_table("combo_items")
    op.drop_index("ix_special_decor_location_id", table_name="special_decor_items")
    op.drop_table("special_decor_items")
    op.drop_index("ix_cakes_location_id", table_name="cakes")
    op.drop_table("cakes")
    op.drop_index("ix_occasions_location_id", table_name="occasions")
    op.drop_table("occasions")
    op.drop_index("ix_slots_plan_id", table_name="slots")
    op.drop_table("slots")
    op.drop_index("ix_plan_gallery_plan_id", table_name="plan_gallery_images")
    op.drop_table("plan_gallery_images")
    op.drop_index("ix_plans_location_id", table_name="plans")
    op.drop_table("plans")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_table("locations")
    op.drop_table("user_roles")
