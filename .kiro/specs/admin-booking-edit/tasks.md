# Implementation Plan: admin-booking-edit

## Overview

This plan implements the admin booking-edit feature backend-first so each layer is testable before the next builds on it: Alembic migrations/models → pure pricing + phone normalization → coupon service → payments void service → request/response schemas → routers (preview, edit, coupon CRUD, combo baselines, payment record/void) → OpenAPI/type generation → admin UI → customer web flow.

Languages are fixed by the design and steering: Python 3.12 / FastAPI / SQLAlchemy 2.0 (sync) / Alembic / psycopg3 for the API, and React 18 + TypeScript + Vite + zod + Vitest for `apps/admin`, Astro + React islands for `apps/web`. Money is integer paise. Pricing is server-authoritative and pure in `services/pricing.py`.

Property tests use Hypothesis with ≥ 100 iterations and a tag comment `Feature: admin-booking-edit, Property N: <text>`. Integration tests use real PostgreSQL. Each top-level task should leave the suite green (`ruff` + `pytest`, and `eslint` + `vitest` where frontend).

Tasks marked with `*` are optional (extra test breadth / stretch) and may be skipped for a faster path; core implementation and the mandatory `tech.md` money/access tests are never optional.

## Tasks

- [x] 1. Alembic migrations 0003–0005 and model changes for booking_items, combo_items, bookings
  - [x] 1.1 Migration 0003 — add quantity and cake weight to booking_items
    - Create `alembic/versions/0003_add_quantity_and_cake_weight_to_booking_items.py`
    - `upgrade`: add `quantity Integer NOT NULL DEFAULT 1` with `CHECK quantity >= 1` named `ck_booking_items_quantity_positive`; add `weight_half_kg SmallInteger NULL` with `CHECK (weight_half_kg IS NULL OR weight_half_kg >= 1)` named `ck_booking_items_weight_positive`
    - Backfill: `UPDATE booking_items SET quantity = 1`; set `weight_half_kg = 1` for `kind='cake'` rows, leave `NULL` otherwise; keep existing `ck_booking_items_kind` unchanged
    - `downgrade`: drop both checks then both columns (reverse order)
    - Update `models/booking_item.py` with the two mapped columns and the two `CheckConstraint`s in `__table_args__`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 12.2, 12.3, 12.4_
    - _Design: Data Models → booking_items; Migration list 0003_

  - [x] 1.2 Migration 0004 — add optional cake/LED baselines to combo_items
    - Create `alembic/versions/0004_add_cake_led_baselines_to_combo_items.py`
    - `upgrade`: add `cake_baseline_paise BigInteger NULL` (`CHECK (cake_baseline_paise IS NULL OR cake_baseline_paise >= 0)` named `ck_combo_items_cake_baseline_nonneg`) and `led_baseline_paise BigInteger NULL` (`CHECK (… >= 0)` named `ck_combo_items_led_baseline_nonneg`); no backfill (NULL = no component)
    - `downgrade`: drop both checks then both columns
    - Update `models/combo_item.py` with both nullable mapped columns and both checks
    - _Requirements: 13.1, 13.2, 13.3, 14.1_
    - _Design: Data Models → combo_items; Migration list 0004_

  - [x] 1.3 Migration 0005 — led_name, coupon snapshot, and nullable email on bookings
    - Create `alembic/versions/0005_add_led_name_coupon_snapshot_and_nullable_email_to_bookings.py`
    - `upgrade`: add `led_name Text NULL`, `coupon_code String NULL`, `coupon_discount_paise BigInteger NOT NULL DEFAULT 0`; **alter `email` from NOT NULL to NULL**; backfill `coupon_discount_paise = 0`
    - `downgrade`: drop the three columns; **backfill null emails to `''` then restore `email` NOT NULL** (documented so the reversal cannot fail)
    - Update `models/booking.py`: `email` → `Mapped[str | None]` / `nullable=True`; add `led_name`, `coupon_code`, `coupon_discount_paise`; leave `phone` nullable at the DB/model level (phone-required is a schema/service rule)
    - _Requirements: 16.2, 20.6, 20.7, 22.3, 22.4, 22.5_
    - _Design: Data Models → bookings; Contact-field schema strategy; Migration list 0005_

  - [ ]* 1.4 Integration test — migrations 0003–0005 apply, downgrade, and backfill
    - Real-Postgres: upgrade 0003–0005 then downgrade cleanly; assert `quantity=1` all rows, `weight_half_kg=1` for cake rows, `coupon_discount_paise=0`; assert `bookings.email` nullable after 0005 and restored to NOT NULL on downgrade (null emails backfilled to `''`)
    - _Requirements: 4.4, 12.4, 16.7, 22.4, 22.5_
    - _Design: Testing Strategy → Real-Postgres integration tests (migrations)_

- [x] 2. Alembic migrations 0006–0009 and model changes for coupons, redemptions, payments, booking_events
  - [x] 2.1 Migration 0006 and model — coupons table
    - Create `alembic/versions/0006_create_coupons_table.py` and `models/coupon.py`
    - Columns per design (`id`, `location_id` FK `ON DELETE RESTRICT`, `code`, `type` `CHECK IN ('flat','percentage')` `ck_coupons_type`, `value` `CHECK >= 0` `ck_coupons_value_nonneg`, `cap_paise` `CHECK (… >= 0)` `ck_coupons_cap_nonneg`, `percentage_base` `CHECK IN ('total','selected_components')` `ck_coupons_percentage_base`, `components JSONB NULL`, `effective_from`, `effective_to`, `is_active`, `one_time`, `total_usage_limit`, `per_customer_limit`, `min_order_paise`, timestamps)
    - Indexes: unique `uq_coupons_location_code` on `(location_id, code)`; `ix_coupons_location_id`
    - `downgrade` drops table (indexes/checks first)
    - _Requirements: 12 (D12), 19.1, 19.2, 19.3, 19.7_
    - _Design: Data Models → coupons; Migration list 0006_

  - [x] 2.2 Migration 0007 and model — coupon_redemptions table
    - Create `alembic/versions/0007_create_coupon_redemptions_table.py` and `models/coupon_redemption.py`
    - Columns: `id`, `coupon_id` FK `ON DELETE CASCADE` (`ix_coupon_redemptions_coupon_id`), `booking_id` FK `ON DELETE CASCADE` with unique `uq_coupon_redemptions_booking`, `customer_key String NOT NULL` (`ix_coupon_redemptions_customer` on `(coupon_id, customer_key)`), `discount_paise BigInteger NOT NULL`, `created_at`
    - `downgrade` drops table
    - _Requirements: 21.4, 21.5_
    - _Design: Data Models → coupon_redemptions; Migration list 0007_

  - [x] 2.3 Migration 0008 and model — relax payments amount check and add reverses FK
    - Create `alembic/versions/0008_relax_payments_amount_check_and_add_reverses_fk.py`
    - `upgrade`: drop `ck_payments_amount_positive`; add `ck_payments_amount_nonzero` (`amount_paise <> 0`); add `reverses_payment_id BigInteger NULL` self-FK `payments.id` `ON DELETE RESTRICT` named `fk_payments_reverses_payment_id` + `ix_payments_reverses_payment_id`
    - `downgrade`: drop index, FK, column; drop `ck_payments_amount_nonzero`; re-add `ck_payments_amount_positive` (`> 0`) — documented to succeed only when no negative rows exist
    - Update `models/payment.py`: add self-FK mapped column; replace the `amount_paise > 0` check with `amount_paise <> 0` (renamed); keep `ck_payments_method`
    - _Requirements: 25.1, 26.1, 26.2_
    - _Design: Data Models → payments; Migration list 0008; 0008 downgrade note_

  - [x] 2.4 Migration 0009 and model — add payment_voided booking event type
    - Create `alembic/versions/0009_add_payment_voided_booking_event_type.py`
    - `upgrade`: drop and re-add `ck_booking_events_type` under the same name including `payment_voided` (`created, accepted, rejected, edited, payment_recorded, payment_voided, expired`)
    - `downgrade`: restore prior list — documented to succeed only when no `payment_voided` rows exist
    - Update `models/booking_event.py`: add `"payment_voided"` to `BOOKING_EVENT_TYPES` and the `ck_booking_events_type` expression
    - _Requirements: 25.9, 26.3_
    - _Design: Data Models → booking_events; Migration list 0009; 0009 downgrade note_

  - [ ]* 2.5 Integration test — migrations 0006–0009 reversible
    - Real-Postgres: upgrade 0006–0009 then downgrade; assert 0008 relaxes amount check / renames it / adds `reverses_payment_id` + index, and its downgrade restores `> 0` (only with no negative rows); assert 0009 adds/removes `payment_voided` from the event-type check
    - _Requirements: 19.7, 21.4, 26.1, 26.2, 26.3, 26.4_
    - _Design: Testing Strategy → Migrations 0008/0009 reversible_

- [x] 3. Pure phone normalization utility (`core/phone.py`)
  - [x] 3.1 Implement `normalize_indian_mobile`
    - Create `app/core/phone.py` with `normalize_indian_mobile(raw) -> str | None`: strip spaces/dashes, drop a single leading `+91`/`91`/`0`, take last 10 digits, return the 10-digit string iff it starts with 6–9 else `None`
    - _Requirements: 23.1, 23.2, 23.4, 23.5_
    - _Design: Phone normalization (Indian mobile)_

  - [x] 3.2 Property test — Indian-mobile normalization is canonical and format-invariant
    - **Property 25: Indian-mobile normalization is canonical and format-invariant**
    - **Validates: Requirements 23.1, 23.2, 23.4, 23.5**
    - Hypothesis ≥100 iters, tag comment; assert `"+91 98765 43210"`, `"098765 43210"`, `"9876543210"` → `"9876543210"`; all formatting variants of a valid mobile map to one canonical key; malformed (too short/long, not 6–9, blank) → `None`
    - _Design: Testing Strategy → Phone normalization_

- [x] 4. Pure pricing engine extensions (`services/pricing.py`)
  - [x] 4.1 Extend value objects and the LED letter count helper
    - In `services/pricing.py` add `LED_UNIT_PRICE_PAISE = 4000`, `led_letter_count`, `COMPONENT_KEYS`, `DecorSelection`, `ComboSelection`, `ValidatedCoupon`; extend `ValidatedRequest` with `cake_weight_half_kg`, `special_decor` selections, `combos` selections, `led_name`; extend `AddonLine` with `unit_price_paise`, `quantity`, `weight_half_kg` and its `amount_paise` property; extend `PriceBreakdown` with `coupon_code`, `coupon_discount_paise`
    - _Requirements: 5.1, 12.1, 16.3, 16.5, 20.6_
    - _Design: Pricing Algorithm → Extended value objects, PriceBreakdown_

  - [x] 4.2 Implement `compute_booking_price` with cake-weight, LED, combo deltas, and coupon stacking
    - Implement the 10 ordered steps: extra-guest charge; decor lines (unit × qty); cake handling (standalone weighted line unless a combo absorbs it); LED handling (standalone unless a combo absorbs it); combo lines (`combo_price + max(0, cake_weighted − cake_baseline) + max(0, led_charge − led_baseline)`); subtotal; admin discount via `_resolve_discount`; pre-coupon total; coupon discount; `total = max(0, …)`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 12.1, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 16.4, 20.4, 20.5_
    - _Design: The compute_booking_price algorithm; Combo/cake/LED interaction_

  - [x] 4.3 Implement `compute_coupon_discount` and `_round_half_up`
    - Flat → `max(0, value)`; percentage → base is pre-coupon total (`total`) or sum of configured component amounts (`selected_components`, mapping plan/extra_guest/decor/combos/cake/food; `other`/`cleaning` excluded); round half-up `(value × base + 50) // 100`; apply cap after rounding
    - _Requirements: 20.3_
    - _Design: Coupon discount computation (pure); Component-to-amount mapping_

  - [x] 4.4 Property test — add-on amount is unit price × quantity
    - **Property 1: Add-on amount is unit price × quantity**
    - **Validates: Requirements 5.1, 12.1, 14.5**

  - [x] 4.5 Property test — subtotal composition
    - **Property 2: Subtotal composition**
    - **Validates: Requirements 5.2**

  - [x] 4.6 Property test — total composition, discount clamp, and clamp-at-zero
    - **Property 3: Total composition, discount clamp, and clamp-at-zero**
    - **Validates: Requirements 5.3, 5.4, 20.4, 20.5**

  - [x] 4.7 Property test — cake weight pricing
    - **Property 4: Cake weight pricing**
    - **Validates: Requirements 12.1, 14.3**

  - [x] 4.8 Property test — LED letter count
    - **Property 5: LED letter count**
    - **Validates: Requirements 16.3, 16.5**

  - [x] 4.9 Property test — combo line price with floored deltas
    - **Property 6: Combo line price with floored deltas**
    - **Validates: Requirements 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 15.5**

  - [x] 4.10 Property test — cake and LED are never double-charged
    - **Property 7: Cake and LED are never double-charged**
    - **Validates: Requirements 13.7, 14.6, 14.7, 14.8, 14.9, 16.4**

  - [x] 4.11 Property test — coupon discount computation
    - **Property 8: Coupon discount computation**
    - **Validates: Requirements 20.3** (include the `other`/`cleaning` never in a `selected_components` base case)

  - [x] 4.12 Property test — pricing is server-authoritative
    - **Property 9: Pricing is server-authoritative**
    - **Validates: Requirements 5.5, 14.10, 16.6, 20.9**

  - [x] 4.13 Unit test — quantity 1 reproduces the pre-quantity single-line price (backward compat)
    - Assert that with `quantity=1` and `cake_weight_half_kg=1` and no combos/LED, `compute_booking_price` reproduces the old single-line price (mandatory `tech.md` server-side price case)
    - _Requirements: 5.1, 5.2_
    - _Design: Testing Strategy → Pure pricing (backward compat)_

  - [x]* 4.14 Unit tests — Requirement 15 worked examples
    - Combo1 "ARUNA"→70000, "SANJAY"→74000; Combo2→90000 at ≤5 letters; Combo3 cake 50000 @0.5kg "ARUNA"→120000, @1.0kg→170000; LED "HAPPY BIRTHDAY"=13; cake ×1/×2/×3; percentage half-up boundary; coupon larger than total clamps to 0
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 16.3_
    - _Design: Testing Strategy → Pure pricing unit (example) tests_

- [x] 5. Coupon service (`services/coupon.py`)
  - [x] 5.1 Implement `resolve_and_validate`
    - Short-circuit order: location match + existence (`CouponInvalidError`), active (`CouponInvalidError`), validity window (`CouponInvalidError`), minimum order (`CouponNotApplicableError`), usage limits one-time/total/per-customer counted from `coupon_redemptions` **excluding this booking's own redemption** (`CouponNotApplicableError`); return a `ValidatedCoupon`; no writes
    - Add `CouponInvalidError` and `CouponNotApplicableError` to `core/errors.py`
    - _Requirements: 20.2, 21.1, 21.2, 21.3, 21.5_
    - _Design: Coupon Service Design → resolve_and_validate; Validation order; Error codes_

  - [x] 5.2 Implement `record_redemption` (upsert keyed on booking_id)
    - Upsert the `coupon_redemptions` row on `booking_id` (via `uq_coupon_redemptions_booking`), storing `customer_key` (Normalized_Phone) and `discount_paise`; re-edit updates, never inserts a second row
    - _Requirements: 21.4, 21.5_
    - _Design: Coupon Service Design → record_redemption; Count semantics_

  - [ ]* 5.3 Property test — coupon redemption is idempotent per booking
    - **Property 22: Coupon redemption is idempotent per booking**
    - **Validates: Requirements 21.4, 21.5** (real-Postgres)

- [x] 6. Payments service — record (reuse) and void (`services/payments.py`)
  - [x] 6.1 Implement `void_payment` (admin-only, reversing entry)
    - Add `PaymentAlreadyVoidedError` and `PaymentNotVoidableError` to `core/errors.py`
    - Validate-before-write in one tx: admin-only (`ForbiddenError`) before any lookup; load + ownership (`NotFoundError`); not a reversal (`PaymentNotVoidableError`); not already voided (`PaymentAlreadyVoidedError`); reason required (`ValidationFailedError`); insert Reversing_Entry (`amount = −original`, `reverses_payment_id`, `method` mirrors original, `note = reason`, `recorded_by_user_id = actor.id`); write one `payment_voided` event; commit; return `list_payments` oldest-first
    - Confirm `record_payment`, `amount_paid_paise`, `derive_amounts(_for_booking)`, `list_payments` are reused unchanged
    - _Requirements: 24.2, 24.3, 24.7, 24.8, 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9_
    - _Design: Payments Service Design → void_payment algorithm; list_payments read model_

  - [ ]* 6.2 Property test — Amount_Paid is the ledger sum and a void nets its original to zero
    - **Property 27: Amount_Paid is the ledger sum, and a void nets its original to zero**
    - **Validates: Requirements 24.2, 24.3, 24.7, 24.8, 24.9, 25.1, 25.2, 25.3** (real-Postgres; mandatory ledger-invariant case: amount due = total − sum(payments), never stored; overpaid → negative due)

  - [ ]* 6.3 Property test — amount due is derived and may be negative
    - **Property 24: Amount due is derived and may be negative**
    - **Validates: Requirements 2.1, 6.3**

- [x] 7. Request/response schemas (`schemas/`)
  - [x] 7.1 Shared selection + breakdown schemas
    - Add `DecorSelectionIn` (`quantity: int = Field(ge=1)`), `ComboSelectionIn`, `AddonLineRead`, `PriceBreakdownRead` (incl. `amount_paid_paise`/`amount_due_paise`)
    - _Requirements: 5.6, 6.2, 6.3_
    - _Design: API Design → Shared selection + breakdown schemas_

  - [x] 7.2 Contact-field rule across booking schemas (phone required, email optional)
    - `BookingCreate`/`AdminBookingCreate`/`BookingUpdate`: `phone` required+non-empty with a `field_validator` running `normalize_indian_mobile` (→ `422` when `None`); `email` optional `str | None`; add `cake_weight_half_kg`, `special_decor`, `combos`, `led_name`, `coupon_code`; PATCH list caveat (`[]` clears, `coupon_code: ""` removes coupon)
    - _Requirements: 3.1, 3.5, 5.6, 10.1, 22.2, 22.3, 23.1, 23.3_
    - _Design: API Design → Changed create/edit request models; Contact-field rule_

  - [x] 7.3 Extend `BookingItemRead` / `BookingRead` detail response
    - `BookingItemRead`: add `quantity`, `weight_half_kg`; `BookingRead`: `phone` always present, `email` optional, add `led_name`, `coupon_code`, `coupon_discount_paise`, `items`, `payments` history, keep derived `amount_paid_paise`/`amount_due_paise`
    - _Requirements: 2.1, 2.2, 7.2, 7.3, 20.7, 24.6, 25.10_
    - _Design: API Design → BookingRead / detail response_

  - [x] 7.4 Coupon and combo authoring schemas; payment void schema
    - `CouponComponents`, `CouponBase` (with `model_validator` enforcing percentage `0..100`), `CouponCreate`, `CouponUpdate`, `CouponRead`; extend combo `ComboCreate`/`ComboRead` with `cake_baseline_paise`/`led_baseline_paise`; extend `PaymentRead` with `reverses_payment_id`, derived `is_voided`, `voided_by_payment_id`; add `PaymentVoidRequest { reason: Field(min_length=1) }`
    - _Requirements: 13.1, 13.6, 19.1, 19.2, 19.6, 25.8, 25.10_
    - _Design: API Design → Admin coupon CRUD, Combo schema, PaymentRead/PaymentVoidRequest_

- [x] 8. Booking service wiring (`services/booking.py`)
  - [x] 8.1 Extend `validate_booking_request` for new inputs and rules
    - Validate phone (blank/missing → `422 VALIDATION_ERROR`; non-normalizable → `422 VALIDATION_ERROR`); cake weight positive multiple of 0.5kg; decor/combo item validity (unknown/inactive/out-of-window/cross-location → `422 ITEM_INVALID`); reject more than one cake-baseline combo and more than one LED-baseline combo (`422 ITEM_INVALID`); build `ValidatedRequest`
    - _Requirements: 5.6, 7.5, 12.5, 22.2, 23.3_
    - _Design: Combo/cake/LED interaction (multiple-baseline rule); Phone normalization usage; Error Handling_

  - [x] 8.2 Wire coupon + Normalized_Phone into preview and save paths
    - Compute `customer_key` from stored `phone` via `normalize_indian_mobile`; call `resolve_and_validate` on preview and save; on save call `record_redemption` in the same tx after pricing; persist `coupon_code`/`coupon_discount_paise`; add `preview_booking` (no DB write) and extend `update_booking`/create for cake weight, LED, quantities, coupon
    - Enforce editable-status (`pending`/`accepted` only; `rejected`/`expired` → `422`); keep slot self-exclusion via `_classify_integrity_error` → `SlotUnavailableError`; write exactly one `edited` audit event
    - _Requirements: 2.1, 6.1, 6.3, 7.1, 7.2, 7.3, 7.4, 7.6, 8.1, 8.2, 8.3, 20.6, 20.7, 21.4, 21.5, 23.5_
    - _Design: Pricing/coupon flow sequence; Coupon Service (customer_key); Error Handling (self-exclusion)_

  - [ ]* 8.3 Property test — booking persistence round-trip
    - **Property 11: Booking persistence round-trip**
    - **Validates: Requirements 2.1, 4.1, 4.3, 4.5, 7.2, 7.3, 12.2, 12.3, 16.2, 20.6, 20.7** (real-Postgres)

  - [ ]* 8.4 Property test — quantity invariant on persisted lines
    - **Property 12: Quantity invariant on persisted lines**
    - **Validates: Requirements 4.2, 4.3** (real-Postgres)

  - [ ]* 8.5 Property test — edit writes exactly one audit event
    - **Property 23: Edit writes exactly one audit event**
    - **Validates: Requirements 7.4** (real-Postgres; mandatory booking-event audit case)

- [x] 9. Routers — preview, edit, coupon CRUD, combo baselines, payment record/void
  - [x] 9.1 Preview endpoints
    - `POST /api/v1/admin/bookings/preview` (`require_role("admin","staff")` + `check_origin`, optional `booking_id` to exclude own redemption) and `POST /api/v1/public/bookings/preview` (public allowlist, rate-limited, `is_customer=True` forces discount 0); both return `PriceBreakdownRead`, no DB write
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 17.2, 18.2, 20.1_
    - _Design: API Design → Preview endpoints_

  - [x] 9.2 Edit + create routers accept new request shape
    - Update `routers/admin/bookings.py` `PATCH /bookings/{id}` and admin create to the `{id, quantity}` selection lists, cake weight, LED, coupon; update `routers/public/bookings.py` create similarly (no admin money fields)
    - _Requirements: 2.1, 3.1, 3.5, 10.1, 17.2, 17.3, 17.4_
    - _Design: API Design → Changed create/edit request models_

  - [x] 9.3 Admin coupon CRUD router (admin-only)
    - Create `routers/admin/coupons.py` with router-level `require_role("admin")`: `POST /coupons`, `PATCH /coupons/{id}`, `GET /coupons?location_id=`; register in `main.py`
    - _Requirements: 19.1, 19.2, 19.3, 19.5, 19.6_
    - _Design: API Design → Admin coupon CRUD_

  - [x] 9.4 Combo authoring baselines in catalog router (admin-only)
    - Extend the admin catalog combo create/edit endpoints to accept/persist `cake_baseline_paise`/`led_baseline_paise`; negative price/baseline → `422`; non-admin → `403`
    - _Requirements: 13.1, 13.4, 13.5, 13.6_
    - _Design: API Design → Combo create/edit schema_

  - [x] 9.5 Payment record (reuse) + void router (admin-only)
    - Keep `POST /api/v1/admin/bookings/{id}/payments` (`require_role("admin","staff")`, staff location-restricted); add `POST /api/v1/admin/payments/{payment_id}/void` with route-level `Depends(require_role("admin"))` and `PaymentVoidRequest`; return the booking's full ledger
    - _Requirements: 24.2, 24.5, 24.9, 25.4, 25.5, 25.8_
    - _Design: API Design → Payments record and void_

  - [x]* 9.6 Integration test — slot conflict with self-exclusion
    - **Property 16: Slot conflict with self-exclusion**
    - **Validates: Requirements 8.1, 8.2, 8.3** (mandatory concurrent/duplicate-slot case)

  - [ ]* 9.7 Integration test — non-editable status is rejected
    - **Property 17: Non-editable status is rejected**
    - **Validates: Requirements 7.6**

  - [x]* 9.8 Integration test — role and location access control
    - **Property 18: Role and location access control**
    - **Validates: Requirements 2.6, 6.6, 9.1, 9.3, 9.4, 9.5** (mandatory role/location access case; unauth→401, non-admin/staff→403, staff cross-location→403, admin cross-location ok)

  - [ ]* 9.9 Integration test — coupon/combo authoring is admin-only with input validation
    - **Property 19: Coupon/combo authoring is admin-only, with input validation**
    - **Validates: Requirements 13.4, 13.5, 13.6, 19.4, 19.5, 19.6**

  - [x]* 9.10 Integration test — invalid catalog item is rejected
    - **Property 15: Invalid catalog item is rejected**
    - **Validates: Requirements 7.5** (mandatory booking-request validation case; includes >1 cake/LED combo)

  - [ ]* 9.11 Integration test — invalid quantity or cake weight is rejected
    - **Property 14: Invalid quantity or cake weight is rejected**
    - **Validates: Requirements 5.6, 6.5, 12.5**

- [x] 10. Coupon, phone-keyed, and preview==save integration tests
  - [x] 10.1 Integration test — invalid coupon is rejected
    - **Property 20: Invalid coupon is rejected**
    - **Validates: Requirements 21.1, 21.2** (real-Postgres)

  - [x] 10.2 Integration test — coupon limit violation is rejected (phone-keyed per-customer)
    - **Property 21: Coupon limit violation is rejected**
    - **Validates: Requirements 20.2, 21.3, 21.5** (real-Postgres; assert per-customer limit counts distinct Normalized_Phone — two formatting variants count as one customer, two real numbers count as two; update any email-keyed coupon test to key on Normalized_Phone)

  - [x] 10.3 Integration test — preview equals save
    - **Property 13: Preview equals save**
    - **Validates: Requirements 6.1, 7.1, 7.3** (real-Postgres; includes cake weight, LED, combo deltas, coupon)

  - [x] 10.4 Integration test — contact fields (phone mandatory, email optional)
    - **Property 26: Blank or invalid phone is rejected**
    - **Validates: Requirements 22.2, 22.3, 23.3** (real-Postgres; blank/missing phone → 422 nothing persisted; non-normalizable → 422; no-email create accepted, persists null email)

  - [x] 10.5 Integration test — both flows apply identical pricing
    - **Property 10: Both flows apply identical pricing**
    - **Validates: Requirements 12.6, 16.8, 17.4** (real-Postgres; public preview/create use same `compute_booking_price`, `is_customer=True` forces discount 0, no admin money accepted)

  - [x]* 10.6 Integration tests — record + void ledger behaviors
    - **Property 28: Void is admin-only and voids at most once** — **Validates: Requirements 25.4, 25.5, 25.6, 25.7, 25.8**
    - **Property 29: A successful void writes exactly one `payment_voided` audit event** — **Validates: Requirements 25.9**
    - Record multiple partial payments sums correctly; overpaid → negative due; bad amount → 422 nothing appended; void nets to zero with original preserved; staff void → 403; void-once; reversal-not-voidable; blank reason → 422

- [x] 11. OpenAPI contract and TypeScript type generation
  - [x] 11.1 Regenerate `apps/admin/src/api/schema.ts` from the OpenAPI schema
    - Run `openapi-typescript` against the updated API; verify breaking request shape (`special_decor`/`combos`, cake weight, LED, coupon, phone/email) and new coupon/payment/void endpoints appear; do not hand-edit types
    - _Requirements: 10.1, 10.2, 10.3_
    - _Design: API Design → Changed create/edit request models (breaking change)_

- [x] 12. Admin UI — bookings list, Edit/create form, summary
  - [x] 12.1 Edit action on the bookings list
    - Add an Edit action to `apps/admin/src/features/bookings/BookingListPage.tsx`/`BookingCard.tsx`, shown only for `pending`/`accepted`, on both mobile card and `md+` table; navigate to the Edit_Form route
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
    - _Design: Non-testable/UI-only criteria R1_

  - [x] 12.2 zod schema mirrors server rules
    - Update `features/bookings/booking-schema.ts`: quantity ≥ 1, non-negative money, **phone required + Indian-mobile pattern, email optional**; `{id, quantity}` selections, cake weight, LED, coupon
    - _Requirements: 5.6, 10.3, 22.1, 22.6_
    - _Design: Frontend tests (zod mirrors)_

  - [x] 12.3 Edit_Form pre-fill + create parity + combo/coupon distinct lines
    - Update `BookingForm.tsx`/`BookingFormPage.tsx` to pre-fill from `BookingRead` (quantities, cake + weight, LED, coupon, phone, optional email, Money_Fields), use the server preview endpoint for the live summary, render each combo and the coupon as distinct lines; identical field set on create and edit; plan change reloads slots and clears invalid slot
    - _Requirements: 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 10.3, 11.1, 11.2, 11.3, 11.4, 11.5, 18.1, 18.2, 18.3_
    - _Design: Non-testable/UI-only criteria R2, R3, R10, R11, R18_

  - [x] 12.4 Payment history, record, and admin-only void UI
    - In the Edit_Form render payment history oldest-first with derived Amount_Paid/Amount_Due, voided payments + their reversing entries; record-payment action; admin-only void action requiring a reason
    - _Requirements: 24.1, 24.6, 25.10_
    - _Design: Non-testable/UI-only criteria R24.1, R24.6, R25.10_

  - [x] 12.5 vitest — zod mirror, pre-fill, distinct lines, phone-required/email-optional
    - Update `booking-schema.test.ts`/`BookingForm.test.tsx`/`PaymentDialog.test.tsx`: zod enforces quantity ≥ 1 / phone-required / email-optional; Edit_Form pre-fills quantities, cake weight, LED, coupon; summary renders combo and coupon as distinct lines
    - _Requirements: 10.3, 11.1, 18.3, 22.6_
    - _Design: Frontend tests_

  - [x] 12.6 Coupon and combo admin screens
    - Add admin screens under `features/catalog/` (or a `coupons/` feature) to create/edit coupons (type, value, cap, percentage base + components, validity, active, limits) and to set combo cake/LED baselines; wire TanStack Query to the new endpoints
    - _Requirements: 13.1, 19.1, 19.2, 19.3_
    - _Design: API Design → Admin coupon CRUD, Combo schema_

- [x] 13. Customer web booking island (`apps/web`)
  - [x] 13.1 Add new customer fields and zod mirror
    - Update the booking React island under `apps/web/src/components/booking/`: cake + Cake_Weight, decor/combo quantities, LED_Name, combo selection as a distinct line, coupon code; **no** admin Money_Fields; zod mirrors phone-required + Indian-mobile pattern and email-optional
    - _Requirements: 10.3, 17.1, 17.2, 17.3, 18.1, 18.2, 18.3, 22.1, 22.6_
    - _Design: Frontend tests (customer island); Non-testable/UI-only R17, R18_

  - [x] 13.2 Wire public preview + create to the live summary
    - Call `POST /api/v1/public/bookings/preview` for the authoritative summary and `POST /api/v1/public/bookings` to submit (ids/quantities/weight/LED/coupon only, never money)
    - _Requirements: 17.2, 17.4, 20.1, 20.9_
    - _Design: API Design → Preview endpoints (public)_

  - [ ]* 13.3 vitest — customer island zod mirror
    - Assert phone-required/email-optional and quantity ≥ 1 mirror the API; combo and coupon render as distinct summary lines
    - _Requirements: 22.1, 22.6, 18.3_

- [x] 14. Final checkpoint — full suite green and mandatory cases pass
  - Run `ruff` and `pytest` (API); run `eslint`, `vitest`, and the production `build` for `apps/admin` and `apps/web`
  - Confirm the `tech.md` mandatory cases pass: concurrent/duplicate booking of the same slot (self-exclusion on edit), server-side price calculation (incl. quantity-1 backward compat), booking-request validation (cross-location/expired/duplicate/unknown item IDs, >1 cake/LED combo), ledger invariant (amount due = total − sum(payments), never stored, overpaid negative), booking-event audit on every state change (`edited`, `payment_voided`), role/location access control, and coupon validation/limits keyed on Normalized_Phone
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (extra property-test breadth / stretch) and can be skipped for a faster path; core implementation tasks and the mandatory `tech.md` money/access tests are never optional.
- Migrations are discrete, ordered `0003 → 0009`, each reversible; the `0005` email-nullability and `0008`/`0009` constraint-tightening-on-downgrade notes are implemented as documented.
- Each property maps to exactly one property-based test tagged `Feature: admin-booking-edit, Property N`, placed close to its implementation to catch errors early.
- Each top-level task should leave the suite green before moving on.
