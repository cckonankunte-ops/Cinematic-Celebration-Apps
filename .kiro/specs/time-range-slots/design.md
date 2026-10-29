# Design — Time-range Slots with Cleaning Buffer, Working Hours, and Late-booking Rules

## Overview

This design replaces label-only slots with **time-range slots** and moves
double-booking prevention from "same `slot_id`" to "**overlapping occupied clock
window**", enforced by a PostgreSQL exclusion constraint. It adds per-location
working hours and a late-booking cutoff + switch, a global cleaning buffer, a
future-start rule (admins exempt), and a safe retrofit of existing data.

Design is anchored to the current architecture: thin routers → services own
transactions and rules → models/migrations own constraints. All times are IST
wall-clock; money/pricing is untouched.

### Key decisions (resolved from requirements)
- **Slot shape:** `start_time TIME` + `duration_minutes SMALLINT`. End is
  computed, never stored (R1).
- **Cleaning buffer:** a single global setting `CLEANING_BUFFER_MINUTES`
  (default 30) in `core/config.py`. *Not* per-location in this phase — simpler,
  matches current ops; can become per-location later without a data migration of
  bookings because the buffer is applied at **conflict-check time**, not stored.
  (One consequence: changing the buffer only affects future conflict checks.)
- **Occupied window is computed, not stored as a range on the row.** We store the
  booking's `start_time` + `duration_minutes` (snapshotted), and the exclusion
  constraint is built on an **expression** `tsrange(anchor, anchor + duration +
  buffer)`. Because the buffer must be a constant inside a constraint expression,
  the buffer used by the DB constraint is a **migration-time constant** seeded
  from config; the service layer uses the same config value for its pre-check and
  error messaging. See "Buffer & the exclusion constraint" for the trade-off.
- **Midnight crossover:** modelled by anchoring each booking to a real
  timestamp built from `booking_date` + `start_time`, and if the computed end is
  ≤ start (wrapped), adding a day. This yields a correct `tsrange` even for
  23:30 + 120 min.
- **Working hours / cutoff / switch:** per-location columns (admin-tunable data).
- **Future-start & end-before-close & cutoff** are **service-layer** rules
  (role- and actor-aware); the **overlap** rule is **DB-enforced** (concurrency).

---

## Architecture

```
Customer web / Admin UI
        │  (slot start+duration, date, role)
        ▼
Routers (public/plans, admin/bookings)         thin: parse + call one service
        ▼
services/booking.py  ── validates, in order, all booking-time rules:
   1. future-start (skip for admin)            [service]
   2. working-hours window (incl. midnight)    [service]
   3. end-before-close (admin may override)    [service]
   4. late-booking cutoff (public only)        [service]
   5. overlap + cleaning buffer                [service pre-check]  → friendly 409
        ▼  INSERT
Postgres  ── exclusion constraint on occupied tsrange   [DB]       → authoritative 409
```

The service pre-check gives clean, specific errors; the DB exclusion constraint
is the race-proof backstop (two concurrent inserts → exactly one wins).

---

## Data model changes

### `slots` (migration: add columns, nullable first)
| column | type | notes |
|---|---|---|
| `start_time` | `TIME` (no tz) | IST wall-clock; minute ∈ {0,30}, sec = 0 |
| `duration_minutes` | `SMALLINT` | > 0 |
| `description` | existing | now optional; derived if blank (R1.3) |

Constraints (added in a later migration, after backfill):
- `CHECK (EXTRACT(MINUTE FROM start_time) IN (0,30) AND EXTRACT(SECOND FROM start_time) = 0)` → `ck_slots_start_half_hour`
- `CHECK (duration_minutes > 0)` → `ck_slots_duration_positive`
- `start_time`, `duration_minutes` set `NOT NULL` once backfilled/verified.

### Duration-based pricing — where the price lives (R11)

Price (and advance, and optionally people allowance / extra-guest) now depend on
`(plan, duration)`. Three options were considered:

- **(A) Put the price on the `slot`.** Each slot already carries the duration, so
  `slots.price_paise` + `slots.advance_paise` directly gives the duration price.
  Simple, no new table. Risk: the same plan+duration may have many slot rows
  (different start times), so the price would be duplicated across them and could
  drift.
- **(B) New `plan_pricing` table keyed by `(plan_id, duration_minutes)`** holding
  only `price_paise` + `advance_paise`. Slots reference a duration; pricing is
  looked up by `(plan_id, slot.duration_minutes)`. No duplication; one price per
  plan+duration. **Chosen.**
- (C) Keep price on the plan and add a per-duration multiplier — rejected (your
  prices aren't a clean multiple; ₹799→₹1199 and ₹1499→₹1999 differ).

**Decision: Option B — a minimal `plan_pricing` table (price + advance only).**

People allowance and the extra-guest charge do **not** vary by duration (Plan 1 =
2 people for both 1h/2h; Plan 2 = 6 for both), so `people_allowed`,
`max_people_allowed`, and `extra_guest_paise` STAY on the `plans` row. Only the
base price and advance move per duration.

```
plan_pricing
  id                bigint pk
  plan_id           fk -> plans(id) on delete cascade
  duration_minutes  smallint          -- matches slot.duration_minutes
  price_paise       bigint not null
  advance_paise     bigint not null
  effective_from / effective_to / is_active   -- same validity pattern as catalog
  unique (plan_id, duration_minutes) where is_active   -- one active price per pair
```

Pricing lookup: for the selected slot, resolve `plan_pricing` by
`(slot.plan_id, slot.duration_minutes)` active on the booking date for the base
price and advance; take `people_allowed` / `max_people_allowed` /
`extra_guest_paise` from the **plan** as today. The existing
`plans.price_paise`/`advance_paise` columns are **retained** (they become the
implicit/legacy 2-hour price and a safety default) but pricing now prefers the
`plan_pricing` row.

`services/pricing.py` change: replace reads of `plan.price_paise` /
`plan.advance_paise` with a resolved `DurationPricing(price_paise,
advance_paise)` looked up from `plan_pricing`; people/extra-guest keep reading
from the plan. All downstream rules (extra-guest, add-ons, discount, coupon,
clamp) are unchanged — only the base price + advance differ. Client still sends
ids only; server authoritative.

Booking snapshot: persist the resolved `plan_price_paise` (already snapshotted
today) and `advance_paise` on the booking from the duration pricing, so history
is stable if `plan_pricing` later changes.

### `locations` (migration: add columns)
| column | type | default | notes |
|---|---|---|---|
| `opens_at` | `TIME` | `'10:00'` | IST |
| `closes_at` | `TIME` | `'01:00'` | IST; may be < opens_at (next day) |
| `last_online_booking_start` | `TIME` | `'22:00'` | public cutoff start |
| `allow_late_booking` | `BOOLEAN` | `false` | switch |

(These are operational, per-branch, admin-tunable — correctly in the DB, not env.)

### `bookings` (migration: add snapshot columns)
| column | type | notes |
|---|---|---|
| `start_time` | `TIME` | snapshot of the slot's start at booking time |
| `duration_minutes` | `SMALLINT` | snapshot of the slot's duration |

Snapshotting mirrors how prices and add-on names are already snapshotted, so a
later slot edit never shifts a historical booking's window.

### `bookings` — replace the unique index with an exclusion constraint

Drop `uq_bookings_active_slot`. Add (requires `btree_gist`):

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE bookings ADD CONSTRAINT excl_bookings_active_overlap
EXCLUDE USING gist (
    location_id WITH =,
    plan_id     WITH =,
    occupied_range WITH &&            -- && = ranges overlap
) WHERE (status IN ('pending','accepted'));
```

where `occupied_range` is a **generated column** (or an expression index target)
of type `tsrange`:

```sql
-- anchor = booking_date + start_time; end = anchor + (duration + BUFFER) minutes;
-- if end <= anchor (wrapped past midnight) the +duration already pushes it to the
-- next calendar instant because we add minutes to a full timestamp, so no manual
-- day-add is needed when anchoring on a timestamp.
occupied_range tsrange GENERATED ALWAYS AS (
    tsrange(
        (booking_date + start_time),
        (booking_date + start_time) + make_interval(mins => duration_minutes + <BUFFER>),
        '[)'
    )
) STORED
```

Design notes:
- Anchoring on `booking_date + start_time` (a full `timestamp`) makes midnight
  crossover automatic: 2026-10-28 23:30 + 150 min = 2026-10-29 02:00. No special
  casing.
- `[)` (half-open) makes back-to-back at the buffer boundary non-overlapping
  (R3.4): A occupies `[15:00, 16:30)`, B `[16:30, …)` do not overlap.
- `&&` is the range overlap operator — this is the range-aware successor to the
  old equality index and keeps the per-`(location, plan, date)` basis (date is
  embedded in the anchor timestamp, so same-plan different-date never overlap).

#### Buffer & the exclusion constraint (the one real trade-off)
A generated column's expression must be immutable, so `<BUFFER>` must be a
**literal baked into the migration**, seeded from `CLEANING_BUFFER_MINUTES` at
migration time. Implications, stated honestly:
- The DB constraint uses the buffer value as of the migration. If ops later
  change `CLEANING_BUFFER_MINUTES`, the **service pre-check** uses the new value
  immediately, but the **DB generated range** still uses the old literal until a
  follow-up migration regenerates the column.
- This is acceptable because the service pre-check is the user-facing gate and
  the DB constraint is the concurrency backstop; a buffer change is rare and
  operationally planned. We document this in the migration and in
  `docs/`. If per-location/live-tunable buffers become a hard requirement, the
  alternative is to **store** `occupied_range` as a plain column written by the
  service (service computes end with the live buffer) and keep the exclusion
  constraint purely structural — chosen against for now to keep a single source
  of truth and avoid a writable range the app could get wrong.

---

## Service-layer rule pipeline

A single helper validates a prospective booking's time, given `(location, slot,
booking_date, actor)`. Order and responsibility:

1. **Future-start (R10):** `if not actor.is_admin and start_dt <= now_ist(): reject`.
   `start_dt = booking_date + slot.start_time` in IST. Future dates always pass;
   today compares against the clock. Admins skip this check.
2. **Working-hours (R5.1–5.4):** the usable window `[start, start+duration]` must
   fit within `[opens_at, closes_at]`, where `closes_at < opens_at` means close is
   next day. Compare using timestamps anchored on the date (+1 day on close when
   wrapped).
3. **End-before-close (R5.5–5.6):** usable end (`start + duration`, **no buffer**)
   must be ≤ close. Reject for customer/staff with the friendly message; an admin
   may override (R6.4, R10 interplay). Buffer may exceed close (R5.6).
4. **Late-booking cutoff (R6):** public only. If `start >= last_online_booking_start`
   and `not allow_late_booking` → not offered / rejected. Staff & admin exempt
   from the cutoff; end-before-close still applies to staff.
5. **Overlap + buffer (R3, R4):** pre-check queries active bookings for the same
   `(location, plan, date)` and rejects on any occupied-range overlap, raising the
   existing `SlotUnavailableError` (409). The INSERT then relies on the exclusion
   constraint as the race backstop; on its `IntegrityError` we classify
   `excl_bookings_active_overlap` → `SlotUnavailableError` (replacing the old
   `uq_bookings_active_slot` classification in `_classify_integrity_error`).

Each rule has its own error code/message so the UI can show something meaningful
(e.g. `BOOKING_ENDS_AFTER_CLOSE`, `LATE_BOOKING_DISABLED`, `START_IN_PAST`,
`SLOT_UNAVAILABLE`).

### Actor/role source
`require_role` already yields the `CurrentUser` with a role; `is_admin` is
derived there. Public endpoints have no actor → treated as "customer" (most
restrictive: future-start + cutoff + end-before-close all apply).

---

## API changes

### Schemas
- `SlotRead` / `SlotAvailabilityRead`: add `start_time` (`"HH:MM"`),
  `duration_minutes`, keep derived `description`, keep `is_available`. The
  availability item's `is_available` now folds overlap+buffer+working-hours+
  cutoff+future-start.
- `SlotAdminCreate` / `SlotAdminUpdate`: accept `start_time` + `duration_minutes`
  (validated :00/:30, >0); `description` optional.
- `LocationRead` / location admin schema: add `opens_at`, `closes_at`,
  `last_online_booking_start`, `allow_late_booking`.
- New error codes in `core/errors.py`: `BookingEndsAfterCloseError (422)`,
  `LateBookingDisabledError (422/409)`, `StartInPastError (422)`,
  `OutsideWorkingHoursError (422)`. `SlotUnavailableError (409)` unchanged.

### Endpoints
- `POST /api/v1/public/plans/{id}/available-slots` — unchanged path; response
  items gain `start_time`/`duration_minutes`; `is_available` now reflects all
  public rules (incl. future-start & cutoff for today).
- Admin slot CRUD (create/update) validates :00/:30, duration, and working-hours
  containment.
- `POST /api/v1/admin/bookings` and `PATCH /.../{id}`: run the rule pipeline with
  the admin actor (future-start & cutoff skipped; end-before-close overridable).
- Location admin update: edit working hours / cutoff / switch (admin only).
  (If no location-edit endpoint exists yet, add a minimal admin one, or set via
  the retrofit/seed + a follow-up; design keeps it admin-only.)

---

## Frontend changes

- **Admin slot management (catalog):** replace the free-text slot field with
  `start_time` (select of :00/:30 options across the location's hours) +
  `duration_minutes` (select: 60/90/120, extensible). Show the derived label.
- **Admin location settings:** fields for open/close, cutoff, and the late switch
  (admin only).
- **Admin booking form & customer wizard:** render slot times from
  start+duration; keep greyed-non-selectable unavailable slots; surface the
  specific rejection messages (ends-after-close, late disabled, start-in-past).
- Display never shows the buffer (R3.3, R7.4).

---

## Retrofit / data migration (R8)

Sequenced for safety (additive → backfill → verify → enforce):

1. **Migration A (additive):** add nullable `slots.start_time`,
   `slots.duration_minutes`, `bookings.start_time`, `bookings.duration_minutes`,
   and the `locations` columns with sensible defaults. No constraints yet.
2. **Backfill script** (`scripts/` one-off, real Postgres):
   - Parse each slot `description` ("9 AM - 12 PM", "6:30 PM - 7:30 PM") →
     `start_time` + `duration_minutes` via a tolerant parser (12-hour, AM/PM,
     optional `:30`, " - " separator).
   - Unparseable descriptions → written to a **report file**, never guessed
     (R8.3). Human maps those, re-runs.
   - Snapshot each existing booking's `start_time`/`duration_minutes` from its
     (now-parsed) slot (R8.4).
   - **Pricing seed (R11):** for each existing plan, create a `plan_pricing` row
     keyed by the plan's predominant existing duration (today's fixed slots are
     2-hour → seed `duration_minutes=120`) using the plan's current
     `price_paise`/`advance_paise`. Admins then add the 1-hour (and other)
     rows via the catalog. Existing bookings already carry a snapshotted
     `plan_price_paise`, so their historical totals are unaffected.
3. **Verify:** assert every active slot and active booking has non-null
   start+duration; run an **overlap pre-check** across existing active bookings
   using the new window math (R8.5). Report any clashes; do not proceed to
   enforce until resolved (business decides per clash).
4. **Migration B (enforce):** set `NOT NULL`, add the :00/:30 and duration CHECKs,
   create `btree_gist`, drop `uq_bookings_active_slot`, add
   `excl_bookings_active_overlap` with the buffer literal. Creation **fails loudly**
   if any residual overlap exists (desired — forces resolution).

Rollback: Migration B down drops the exclusion constraint and restores the old
unique index; Migration A down drops the columns. The buffer literal and the
restored index are documented.

---

## Error handling

| Condition | Code | HTTP | Who |
|---|---|---|---|
| start ≤ now (today) | `START_IN_PAST` | 422 | customer, staff (not admin) |
| outside open/close | `OUTSIDE_WORKING_HOURS` | 422 | all |
| usable end > close | `BOOKING_ENDS_AFTER_CLOSE` | 422 | customer, staff (admin override) |
| post-cutoff & switch off | `LATE_BOOKING_DISABLED` | 422 | public only |
| window overlaps active | `SLOT_UNAVAILABLE` | 409 | all (DB backstop) |
| :15/:45 start | validation | 422 | all |

All follow the `{ "error": { "code", "message" } }` envelope.

---

## Testing strategy (real Postgres; maps to mandatory cases)

Integration (Postgres/testcontainers):
- Overlapping 1h & 2h same plan/date → exactly one booked.
- Concurrent identical-window requests → exactly one wins (exclusion constraint).
- Back-to-back at buffer boundary → both allowed; inside buffer → rejected.
- Working-hours boundary incl. midnight crossover (23:30+120 ok; 02:00 start ko).
- End-after-close: 00:00+120 (close 01:00) rejected w/ message; 00:00+60 ok;
  admin override allowed.
- Late cutoff: public blocked when off, allowed when on; admin/staff exempt from
  cutoff; staff still bound by end-before-close.
- Future-start: customer/staff past-start rejected; admin past-start allowed;
  availability hides passed slots for today.
- `:00/:30` validation at app and DB (CHECK) layers.

Unit:
- The time-rule pipeline (pure function over `(location, slot, date, actor, now)`)
  — each rule independently + composed ordering.
- Description parser: known formats → times; unparseable → flagged.

Retrofit:
- Parser over a fixture of real descriptions; report path for failures.
- Overlap pre-check surfaces a seeded clash.

Frontend (vitest): availability rendering (greyed unavailable), slot time display
from start+duration, buffer never shown, rejection messages surfaced.

---

## Open items for the tasks phase
- Confirm whether a location-edit admin endpoint/screen exists or must be added
  (working hours/cutoff/switch need an entry point).
- Decide the duration options exposed in the UI (60/90/120 initially).
- Confirm the seeded buffer literal for Migration B equals the config default (30).
