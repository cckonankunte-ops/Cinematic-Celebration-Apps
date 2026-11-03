# Requirements — Per-branch Booking Mode (Slot picker vs Slotless start+duration)

## Introduction

Today every booking is tied to a pre-configured **slot row** (`slot_id`) for a
plan. After the time-range-slots work, a slot is a `(start_time,
duration_minutes)` on a date, and double-booking is prevented by an overlap
exclusion constraint on the occupied clock window. Pre-creating one slot per
start time × duration (10:00/10:30/11:00… × 1h/2h) produces a long, confusing
dropdown for staff and customers.

This feature lets **each branch (location) choose how its booking window is
produced**, via an admin-set per-location **booking mode**:

- **Mode A — slot-backed (current behaviour):** the admin configures slot rows;
  a booking carries a real `slot_id`; the booking UIs pick from those slots.
- **Mode B — slotless (open):** no per-start-time slot rows. The user picks a
  **duration** (which drives `plan_pricing`) and a **start time** (:00/:30)
  generated from the branch's working hours; the server validates the raw
  `(start_time, duration_minutes)` directly, with no `slot_id`.

Both modes converge on the same underlying truth already built in
time-range-slots: a booking occupies `[start, start + duration +
cleaning_buffer)` on a date, validated by the existing time-rule pipeline
(future-start, working-hours, end-before-close, same-day late cutoff) and the
overlap exclusion constraint, and priced by duration via `plan_pricing`. Only
the **source** of `(start, duration)` differs between modes.

Money, pricing rules, the cleaning buffer, the time-rule pipeline, and the
booking lifecycle are unchanged. This spec is about where the booking window
comes from and how the UIs present it — not about changing how a window is
validated or priced.

### Non-goals
- No change to pricing math, the cleaning buffer, or the overlap/validation
  rules themselves.
- No removal of Mode A (slot-backed) — it remains the default and fully
  supported.
- No change to the customer-facing money contract (still integer paise;
  server-authoritative).

## Glossary
- **Booking mode**: a per-location setting, `slot` or `open`, controlling how the
  booking window is produced.
- **Slot mode (A)**: booking references a configured slot row (`slot_id`).
- **Open mode (B)**: booking carries `start_time` + `duration_minutes` directly;
  no `slot_id`.
- **Duration options**: the admin-priced durations for a plan (from
  `plan_pricing`, e.g. 60/120 minutes), which drive both the selectable
  durations and the base price in open mode.

---

## Requirement 1 — Per-location booking mode setting

**User Story:** As an admin, I want to set each branch to either slot-based or
open booking, so each branch uses the booking UX that suits it.

### Acceptance Criteria
1. Each location SHALL have a `booking_mode` with values `slot` or `open`,
   defaulting to `slot` (preserving current behaviour for every existing
   location after migration).
2. WHERE an admin updates a location THEN the system SHALL allow setting
   `booking_mode` via the existing admin location-settings endpoint
   (`require_role("admin")`); staff SHALL NOT be able to change it (403).
3. THE booking UIs (admin booking form and customer wizard) SHALL read the
   selected location's `booking_mode` and render the matching flow.
4. Changing a location's mode SHALL NOT alter or invalidate any existing
   booking (historical bookings keep their stored `start_time`/
   `duration_minutes`, and `slot_id` if present).
5. THE `booking_mode` is a simple **current switch**, not a date-scheduled
   setting: an admin MAY toggle it between `slot` and `open` at any time and any
   number of times (e.g. Mode A for a month, Mode B for a few days, then back).
   The current value governs only how NEW bookings are created from that point
   on; it does not apply retroactively and is not keyed to the booking date.
6. Bookings created under different modes SHALL coexist safely for the same
   location: a slot-mode booking (with `slot_id`) and an open-mode booking
   (null `slot_id`) both occupy their clock window and are enforced by the same
   overlap constraint, regardless of the location's current mode.

**Test cases**
- Default after migration: every existing location has `booking_mode = 'slot'`.
- Admin can PATCH `booking_mode` to `open` and back repeatedly; staff PATCH → 403.
- Switching a branch to `open` leaves its existing bookings intact and readable.
- A slot-mode booking and an open-mode booking on the same location/plan/date
  with overlapping windows conflict (exactly one wins), proving cross-mode
  coexistence is enforced by the shared overlap constraint.

## Requirement 2 — Slot mode (A) unchanged

**User Story:** As a branch that curates its slots, I want slot-based booking to
work exactly as before, so nothing regresses.

### Acceptance Criteria
1. WHERE a location's mode is `slot` THEN booking create/edit/preview (public and
   admin) SHALL behave exactly as today: a valid `slot_id` is required, and the
   booking snapshots `start_time`/`duration_minutes` from that slot.
2. THE availability endpoint SHALL continue to return the location's active
   slots with `is_available`, as today.
3. All existing slot-mode behaviour (overlap, buffer, working-hours, future-start,
   end-before-close, same-day cutoff, duration pricing) SHALL be unchanged.

**Test cases**
- Existing slot-mode integration tests continue to pass unchanged.
- A slot-mode booking still requires a valid `slot_id` (missing/invalid → 422).

## Requirement 3 — Open mode (B): slotless booking by duration + start time

**User Story:** As a branch that prefers open booking, I want staff/customers to
pick a duration and a start time directly, so we don't maintain dozens of slot
rows.

### Acceptance Criteria
1. WHERE a location's mode is `open` THEN booking create/edit/preview SHALL accept
   `start_time` (:00/:30, seconds zero) and `duration_minutes` directly, with no
   `slot_id`.
2. THE server SHALL reject an open-mode request that omits `start_time` or
   `duration_minutes`, or whose `start_time` is not on the hour/half-hour (422).
3. THE `duration_minutes` offered SHALL be the plan's priced durations (active
   `plan_pricing` rows for that plan on the date); selecting one SHALL set the
   base price from that `plan_pricing` row (R11 behaviour, reused).
4. An open-mode booking SHALL run the SAME time-rule pipeline (future-start,
   working-hours, end-before-close, same-day late cutoff) and the SAME
   overlap + cleaning-buffer check as slot mode, with the actor's role honoured
   (admin exemptions apply as today).
5. An open-mode booking SHALL persist `start_time` + `duration_minutes` on the
   booking with `slot_id` null.
6. WHERE a location is in `slot` mode THEN an open-mode request (start+duration,
   no slot_id) SHALL be rejected, and vice versa, so a request always matches the
   location's mode (422 with a clear message).

**Test cases**
- Open-mode create: valid start+duration → booking persisted with slot_id null.
- Open-mode rejects missing start/duration and non-:00/:30 starts (422).
- Open-mode overlap: two overlapping windows → exactly one wins (409), identical
  to slot mode.
- Open-mode honours working-hours / end-before-close / future-start / same-day
  cutoff with the same role rules.
- Mode mismatch: open-mode payload against a slot-mode location → 422 (and the
  reverse).

## Requirement 4 — Open-mode availability (start-time generation)

**User Story:** As a customer/staff in open mode, I want to see which start times
are free for my chosen duration, so I pick a valid, non-conflicting time.

### Acceptance Criteria
1. THE system SHALL provide an availability query for open mode that, given a
   location, plan, date, and `duration_minutes`, returns the candidate :00/:30
   start times across the branch's working hours, each annotated with
   `is_available`.
2. A candidate start SHALL be unavailable when its occupied window (incl. the
   cleaning buffer) overlaps an active booking, or when it fails a public time
   rule (working-hours, end-before-close, future-start for today, same-day
   cutoff) for the requesting actor.
3. THE buffer SHALL NEVER be shown to the user (same rule as today); only the
   usable window is presented.
4. WHERE the location is in `slot` mode THEN this open-mode availability query
   SHALL NOT be used by the UI (the existing slot availability endpoint is used
   instead).

**Test cases**
- Generation covers :00/:30 starts within working hours for the chosen duration.
- A held window (incl. buffer) marks the overlapping candidate starts
  unavailable; a back-to-back start exactly at the buffer boundary is available.
- Post-cutoff same-day starts are unavailable to the public when the switch is
  off; future-date starts stay available.

## Requirement 5 — Booking UIs adapt to mode

**User Story:** As a customer and as staff, I want the booking screen to match
the branch's mode, so the flow is clear.

### Acceptance Criteria
1. WHERE mode is `slot` THEN the admin booking form and customer wizard SHALL
   render the existing slot picker.
2. WHERE mode is `open` THEN they SHALL render a **duration** selector (the
   plan's priced durations) and a **start-time** picker generated from working
   hours, greying out/disabling unavailable starts, and SHALL show the
   duration-specific base price and re-price the preview when the duration or
   start changes.
3. Both modes SHALL surface the same specific rejection messages (ends-after-
   close, late-disabled, start-in-past, slot/overlap unavailable) and SHALL never
   show the buffer.
4. THE admin location-settings screen SHALL expose the `booking_mode` toggle
   (admin only).

**Test cases (frontend)**
- Slot-mode location renders the slot dropdown; open-mode renders
  duration + start-time pickers.
- Open-mode: changing duration re-prices; selecting a greyed start is blocked.
- Mode toggle visible/editable only to admins.

## Requirement 6 — Data model & migration (back-compatible)

**User Story:** As an operator, I want the mode change rolled out without
touching existing bookings, so nothing breaks.

### Acceptance Criteria
1. A migration SHALL add `locations.booking_mode` (text + CHECK `in
   ('slot','open')`, NOT NULL, server default `'slot'`).
2. A migration SHALL make `bookings.slot_id` **nullable** (open-mode bookings
   store null); the FK and its ON DELETE behaviour are otherwise unchanged.
3. THE overlap exclusion constraint and `occupied_range` generated column SHALL
   continue to apply to all active bookings regardless of mode (they key on
   location/plan/date/window, not on `slot_id`).
4. Existing bookings and slots SHALL be unaffected; existing locations default to
   `slot`.

**Test cases**
- Migration up: `booking_mode` column present, default `slot`; `slot_id`
  nullable; existing rows intact.
- Overlap constraint still rejects an overlapping active insert when `slot_id`
  is null (open mode).

---

## Mandatory test coverage (per tech.md)
Because this touches booking integrity and money:
- Concurrent booking of the same window in **open mode** (exactly one wins).
- Server-side price calculation in open mode (duration drives base price;
  client base ignored).
- Booking-request validation in open mode (missing/invalid start+duration,
  mode mismatch, cross-location/expired/unknown IDs rejected).
- Overlap + buffer parity between slot and open modes.
- Role/location access control for the `booking_mode` toggle (admin only).
- No regression of all existing slot-mode integrity/role/pricing tests.
