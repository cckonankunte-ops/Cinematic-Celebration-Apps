# Implementation Plan — Per-branch Booking Mode

Sequencing is safety-first: additive schema → optional-window schemas → service
window-resolution branch (reusing the existing rule pipeline) → open-mode
availability → frontend → full gate. Backend before frontend. Real PostgreSQL
for integration tests. Money/pricing rules, cleaning buffer, time pipeline, and
the overlap constraint are reused unchanged — only the window SOURCE differs.

- [x] 1. Model + migration (additive, back-compatible)
  - [x] 1.1 `Location` model: add `booking_mode: Mapped[str]` (default `'slot'`,
    server default `'slot'`).
  - [x] 1.2 `Booking` model: make `slot_id` nullable (`Mapped[int | None]`);
    keep the FK + `ON DELETE RESTRICT`. Do NOT touch `start_time`/
    `duration_minutes` (remain the authoritative window).
  - [x] 1.3 Alembic `0013_add_booking_mode_and_nullable_slot_id`: add
    `locations.booking_mode` (TEXT NOT NULL default `'slot'`) +
    `ck_locations_booking_mode CHECK (booking_mode IN ('slot','open'))`; drop
    NOT NULL on `bookings.slot_id`. Additive; no data backfill.
  - [x] 1.4 Integration test: migration leaves existing rows intact; new
    locations default to `slot`; `slot_id` accepts null.
  - _Requirements: 1.1, 6.1, 6.2, 6.4_

- [x] 2. Schemas: optional window + mode-structural validation
  - [x] 2.1 `PreviewBase` / `BookingCreate` (→ admin/public preview,
    `AdminBookingCreate`): `slot_id: int | None = None`; add
    `start_time: time | None` (validator :00/:30, sec 0) and
    `duration_minutes: int | None` (>0).
  - [x] 2.2 `BookingUpdate`: add `start_time`/`duration_minutes` (optional) for
    editing an open-mode window.
  - [x] 2.3 Structural validator: reject a request carrying BOTH `slot_id` AND
    (`start_time`/`duration_minutes`) (ambiguous → 422). (Mode-match is enforced
    in the service, task 3.)
  - [x] 2.4 `BookingRead`: `slot_id: int | None`.
  - [x] 2.5 `LocationRead` + `LocationAdminRead` + location admin update schema:
    expose/accept `booking_mode`.
  - _Requirements: 2.1, 3.1, 3.2, 6.2_

- [x] 3. Service: window resolution branch (the one new seam)
  - [x] 3.1 Add `resolve_booking_window(db, location, plan_id, *, slot_id,
    start_time, duration_minutes, booking_date) -> WindowResolution` in
    `services/booking.py`:
    - slot mode → require/load/validate slot (existing `_load_valid_slot`);
      window from slot; persisted `slot_id` = slot.id; reject start+duration
      (mode mismatch 422).
    - open mode → require start+duration (validate :00/:30, >0); window from
      request; persisted `slot_id` = None; reject `slot_id` (mode mismatch 422);
      require an active `plan_pricing` row for `(plan, duration, date)`.
  - [x] 3.2 Wire `resolve_booking_window` into `create_customer_booking`,
    `create_admin_booking`, and `preview_booking`, replacing inline
    `_load_valid_slot` + `_slot_timing`. Keep `_enforce_booking_time`,
    `_assert_no_overlap`, and `resolve_duration_pricing` calls unchanged
    (shared by both modes).
  - [x] 3.3 `update_booking`: allow editing `start_time`/`duration_minutes` for
    open-mode bookings (re-resolve window, re-run time pipeline + overlap
    pre-check with self-exclusion, re-price by duration); unchanged for slot
    mode.
  - [x] 3.4 `validate_booking_request`: stop hard-requiring a slot (item
    validation stays; window handled by `resolve_booking_window`).
  - [x] 3.5 Read mapper: derive a time-range label for open-mode bookings
    (slot_id null) from `start_time`+`duration_minutes` for lists/WhatsApp.
  - _Requirements: 2.1, 2.3, 3.1, 3.3, 3.4, 3.5, 3.6_

- [x] 4. Open-mode availability (start-time generation)
  - [x] 4.1 `services/catalog` (or a new `services/open_availability`):
    `generate_open_availability(db, plan_id, location_id, on, duration_minutes,
    *, actor, now)` → list of `{ start_time, is_available }` for :00/:30 starts
    across working hours (reuse `working_window`, `occupied_window`,
    `_active_occupied_windows`, `validate_booking_time`). Buffer never exposed.
  - [x] 4.2 Endpoint `POST /api/v1/public/plans/{plan_id}/open-availability`
    (public allowlist) + the admin-actor path for the admin booking form.
  - [x] 4.3 Integration tests: candidate generation within hours; held window
    (incl. buffer) marks overlapping starts unavailable; back-to-back at buffer
    boundary available; same-day post-cutoff hidden for public, future-date
    available; admin exemptions.
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 5. Location mode admin endpoint
  - [x] 5.1 Accept `booking_mode` in the admin location update
    (`require_role("admin")`); return it in `LocationAdminRead`.
  - [x] 5.2 Integration tests: admin can set `slot`↔`open` repeatedly; staff
    → 403; value constrained to the two allowed values.
  - _Requirements: 1.2, 1.5_

- [x] 6. Booking integrity tests (mandatory, real Postgres)
  - [x] 6.1 Open-mode concurrent identical-window inserts → exactly one wins
    (DB exclusion constraint with null `slot_id`).
  - [x] 6.2 Cross-mode overlap: a slot-mode booking and an open-mode booking on
    the same (location, plan, date) with overlapping windows conflict.
  - [x] 6.3 Open-mode pricing: duration drives base price; client base ignored;
    duration with no active `plan_pricing` row → rejected.
  - [x] 6.4 Open-mode validation: missing/invalid start+duration, non-:00/:30,
    and mode mismatch both directions → 422.
  - [x] 6.5 Time-rule parity in open mode (working-hours, end-before-close,
    future-start, same-day cutoff) with role exemptions.
  - _Requirements: 1.6, 2.1, 3.2, 3.3, 3.4, 3.6, 4.2, mandatory tech.md cases_

- [ ]* 6.6 Property-based tests for window resolution + parity
  - PBT over random (mode, slot vs start+duration, :00/:30, duration, date, now,
    role): assert slot and open modes produce identical validation/pricing
    outcomes for the same resolved window; mode mismatch always rejected.
  - _Requirements: 2.3, 3.3, 3.6_

- [x] 7. Frontend — location settings mode toggle
  - `booking_mode` select (Slot / Open) in `LocationSettings.tsx`, admin-only,
    via the existing location update. Vitest for admin-only + value mapping.
  - _Requirements: 1.2, 5.4_

- [x] 8. Frontend — booking form + customer wizard adapt to mode
  - [x] 8.1 Read the selected location's `booking_mode`; slot mode → existing
    slot picker (unchanged).
  - [x] 8.2 Open mode → Duration selector (plan's priced durations) + Start-time
    picker from the open-availability query; grey out unavailable starts; show
    the duration base price; re-price the preview on duration/start change;
    surface the same rejection messages; never show the buffer.
  - [x] 8.3 Send `slot_id` OR `start_time`+`duration_minutes` by mode in
    preview/create/edit payloads.
  - [x] 8.4 Vitest: mode-driven rendering; open-mode re-pricing; disabled start
    selection; payload shape per mode.
  - _Requirements: 3.1, 5.1, 5.2, 5.3_

- [x] 9. Docs + .env.example + regenerate API types
  - Document the booking-mode switch + open-mode flow in `docs/`; note the
    nullable-`slot_id` and mode-match decisions. Run `gen:api` so admin/web
    types match the new schema.
  - _Requirements: all; structure.md Definition of Done_

- [x] 10. Full verification gate
  - `ruff`, `pytest` (incl. all mandatory integrity/role cases + slot-mode
    regression), `eslint`, `vitest`, both builds green.
  - _Requirements: all; tech.md Definition of Done_
