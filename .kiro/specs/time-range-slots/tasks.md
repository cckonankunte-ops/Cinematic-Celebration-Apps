# Implementation Plan — Time-range Slots

Sequencing is safety-first: additive schema → backfill/verify data → enforce
constraints. Backend before frontend. Real PostgreSQL for all integration tests.
Money/pricing untouched. Times are IST wall-clock.

- [ ] 1. Config + error codes groundwork
  - Add `CLEANING_BUFFER_MINUTES: int = 30` to `core/config.py`; add to
    `.env.example` with a comment.
  - Add new error classes in `core/errors.py`: `StartInPastError` (422),
    `OutsideWorkingHoursError` (422), `BookingEndsAfterCloseError` (422),
    `LateBookingDisabledError` (422). Keep `SlotUnavailableError` (409).
  - _Requirements: 3.1, 9.1, 9.3; error table in design_

- [ ] 2. Models: additive columns (nullable)
  - [ ] 2.1 `Slot` model: add `start_time: Mapped[time | None]`,
    `duration_minutes: Mapped[int | None]`; keep `description` (now optional).
  - [ ] 2.2 `Location` model: add `opens_at`, `closes_at`,
    `last_online_booking_start` (`time`, with defaults 10:00/01:00/22:00) and
    `allow_late_booking: bool = False`.
  - [ ] 2.3 `Booking` model: add snapshot `start_time`, `duration_minutes`
    (nullable for now). Do NOT touch the existing index yet.
  - _Requirements: 1.1, 1.5, 5.1, 5.3, 6.1, 8.1, 8.4_

- [ ] 2.4 `PlanPricing` model (duration-based pricing, R11)
  - New `plan_pricing` entity: `plan_id`, `duration_minutes`, `price_paise`,
    `advance_paise`, validity + `is_active`; unique `(plan_id, duration_minutes)`
    where active. People/extra-guest stay on `plans` (not per duration). Keep
    plan-level price columns as fallback.
  - _Requirements: 11.1, 11.3, 11.4_

- [ ] 3. Migration A — additive schema
  - Alembic `0011_add_time_range_slot_columns`: add the nullable slot/booking
    columns and the location columns (with server defaults); create the
    `plan_pricing` table. No constraints on the new slot/booking columns, no
    index changes to `bookings`. Include `CREATE EXTENSION IF NOT EXISTS
    btree_gist`.
  - _Requirements: 8.1, 11.3_

- [ ] 4. Pure time utilities + rule pipeline (unit-tested)
  - [ ] 4.1 `services/slots.py` helpers: `usable_end(start, duration)`,
    `occupied_end(start, duration, buffer)`, `window_fits_working_hours(...)`,
    midnight-crossover anchoring to `booking_date + start_time`.
  - [ ] 4.2 `validate_booking_time(location, slot, booking_date, actor, now_ist)`
    applying rules in order: future-start (admin-exempt), working-hours,
    end-before-close (admin-override), late-cutoff (public-only). Returns/raises
    the specific error.
  - [ ] 4.3 Unit tests for each rule independently and composed (incl. midnight,
    close-crossing, admin exemptions).
  - _Requirements: 2.3, 5.2, 5.4, 5.5, 5.6, 6.2, 6.3, 6.4, 10.1, 10.2, 10.3_

- [ ] 5. Slot description parser (retrofit core) + unit tests
  - `scripts/migrate_time_slots/parse.py`: tolerant parser for "9 AM - 12 PM",
    "6:30 PM - 7:30 PM" → `(start_time, duration_minutes)`; returns None on
    low-confidence. Unit tests over a fixture of real descriptions incl.
    unparseable samples.
  - _Requirements: 8.2, 8.3_

- [ ] 6. Backfill script (one-off, real Postgres)
  - `scripts/migrate_time_slots/backfill.py`: parse every slot description,
    write start/duration; snapshot onto each existing booking from its slot;
    write an **unparseable report** file; never guess.
  - Add an **overlap pre-check** pass that reports existing active bookings whose
    new occupied windows overlap (per location/plan/date).
  - **Seed `plan_pricing`:** for each plan, insert a row at the predominant
    existing duration (2h → 120) from the plan's current price/advance (R11
    retrofit).
  - _Requirements: 8.2, 8.3, 8.4, 8.5, 8.6, 11.3_

- [ ] 6.1 Duration-based pricing in `services/pricing.py`
  - Introduce `DurationPricing(price_paise, advance_paise)`; resolve it from
    `plan_pricing` by `(plan_id, slot.duration_minutes)` active on the date,
    falling back to the plan's `price_paise`/`advance_paise` when no row exists.
  - `compute_booking_price` reads the base price + advance from `DurationPricing`;
    people allowance and extra-guest keep reading from the plan. All other rules
    unchanged. Server authoritative; client base ignored.
  - Unit tests: plan1/1h=799, plan1/2h=1199, plan2/1h=1499, plan2/2h=1999;
    extra-guest/add-ons stack on the right base; fallback to plan-level when no
    duration row.
  - _Requirements: 11.1, 11.2, 11.4, 11.7_

- [ ] 7. Admin slot CRUD: start_time + duration
  - [ ] 7.1 `schemas/catalog_admin.py`: `SlotAdminCreate`/`SlotAdminUpdate` accept
    `start_time` (validator: minute ∈ {0,30}, sec 0) + `duration_minutes` (>0);
    `description` optional (derive when blank).
  - [ ] 7.2 `services/catalog_admin.py`: create/update persist the new fields and
    reject slots whose usable window falls outside the location's working hours.
  - [ ] 7.3 `SlotRead`/`SlotAvailabilityRead` + admin read schema: expose
    `start_time`, `duration_minutes`, derived `description`.
  - [ ] 7.4 Integration tests: :00/:30 validation; duration>0; outside-hours slot
    rejected.
  - [ ] 7.5 `plan_pricing` admin CRUD: schemas + service + endpoints to set
    price/advance per `(plan, duration)`; admin-only; integration tests incl.
    unique-active-pair enforcement.
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.3, 5.2, 11.3, 11.5_

- [ ] 8. Availability endpoint: overlap + buffer + public rules
  - Update `services/catalog.list_slots_with_availability` to compute
    `is_available` from: overlap (incl. buffer) against active bookings,
    working-hours, future-start (today), and late-cutoff for public.
  - Integration tests: held window (incl. buffer) marks slot unavailable;
    post-cutoff slots hidden for public when switch off; past-start slots hidden
    for today.
  - _Requirements: 3.2, 3.3, 3.4, 4.1, 4.3, 6.2, 7.1, 7.2, 7.4, 10.4_

- [ ] 9. Booking create/edit: rule pipeline + overlap pre-check
  - [ ] 9.1 In `create_admin_booking` / public create / edit: snapshot
    `start_time`+`duration_minutes` onto the booking; resolve duration pricing and
    snapshot `plan_price_paise`/`advance_paise` from it (R11); run
    `validate_booking_time` with the actual actor (admin exemptions honored).
  - [ ] 9.2 Overlap pre-check raises `SlotUnavailableError` before INSERT;
    `_classify_integrity_error` maps `excl_bookings_active_overlap` →
    `SlotUnavailableError` (replace `uq_bookings_active_slot`).
  - [ ] 9.3 Integration tests: overlapping 1h/2h → one wins; back-to-back at
    buffer ok; end-after-close rejected (admin override ok); future-start role
    rules; outside-hours rejected.
  - _Requirements: 3.4, 4.1, 4.3, 4.4, 5.5, 5.6, 6.4, 10.1, 10.2_

- [ ]* 9.4 Property-based tests for the rule pipeline
  - PBT over random (start ∈ :00/:30, duration, date, now, role, working window):
    assert invariants — admin never blocked by future/cutoff; usable-end-after-
    close always rejected for non-admin; buffer boundary is inclusive-exclusive.
  - _Requirements: 3.4, 5.5, 10.1, 10.2_

- [ ] 10. Migration B — enforce constraints (after backfill/verify)
  - Set slot/booking `start_time`,`duration_minutes` `NOT NULL`; add
    `ck_slots_start_half_hour`, `ck_slots_duration_positive`.
  - Add generated `occupied_range` + `excl_bookings_active_overlap`
    (`btree_gist`, buffer literal seeded from config=30); drop
    `uq_bookings_active_slot`. Creation must fail if residual overlaps exist.
  - Integration test: concurrent identical-window inserts → exactly one wins.
  - _Requirements: 2.2, 4.2, 4.5, 8.1, 8.5_

- [ ] 11. Location working-hours/cutoff admin
  - [ ] 11.1 `LocationRead` + location admin update schema expose/accept
    `opens_at`, `closes_at`, `last_online_booking_start`, `allow_late_booking`.
  - [ ] 11.2 Admin-only endpoint to update a location's hours/cutoff/switch
    (add if none exists); enforce `require_role("admin")`.
  - [ ] 11.3 Integration tests: staff cannot edit (403); admin can; cutoff/switch
    affect public availability.
  - _Requirements: 5.1, 5.3, 6.1, 6.5, 9.2_

- [ ] 12. Frontend — admin slot management + per-duration pricing
  - Catalog slot form: `start_time` select (:00/:30 within hours) +
    `duration_minutes` select (60/90/120); show derived label.
  - Catalog plan pricing UI: edit price/advance per `(plan, duration)` in rupees
    → paise. Vitest for form mapping/validation.
  - _Requirements: 1.3, 2.1, 7.3, 11.5_

- [ ] 13. Frontend — location settings (admin)
  - Fields for open/close, cutoff, late switch (admin only). Vitest.
  - _Requirements: 5.1, 6.1_

- [ ] 14. Frontend — booking form + customer wizard
  - Render slot times from start+duration; show the duration-specific base price
    and re-price the preview/total when the duration changes (R11.6); keep
    greyed/non-selectable unavailable slots; surface specific rejection messages
    (ends-after-close, late-disabled, start-in-past); never show the buffer.
    Vitest for display + re-pricing + message surfacing.
  - _Requirements: 3.3, 7.2, 7.3, 7.4, 5.5, 6.2, 10.1, 11.6_

- [ ] 15. Docs + .env.example + regenerate API types
  - Document the buffer-literal-in-migration trade-off and the retrofit runbook
    in `docs/`; ensure `.env.example` carries `CLEANING_BUFFER_MINUTES`.
  - Run `gen:api` so admin/web types match the new schema.
  - _Requirements: 9.3_

- [ ] 16. Full verification gate
  - `ruff`, `pytest` (incl. all mandatory integrity/role cases), `eslint`,
    `vitest`, both builds green.
  - _Requirements: all; tech.md Definition of Done_
