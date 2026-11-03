# Design — Per-branch Booking Mode (Slot picker vs Slotless start+duration)

## Overview

A per-location `booking_mode` (`slot` | `open`, default `slot`) selects how a
booking's time window is produced. Both modes converge on the same invariant
already built in time-range-slots: a booking occupies
`[start, start + duration + cleaning_buffer)` on a date, validated by the shared
time-rule pipeline and the `excl_bookings_active_overlap` exclusion constraint,
and priced by duration via `plan_pricing`. The **only** difference is the source
of `(start_time, duration_minutes)`:

- **Slot mode (A):** read from a configured `Slot` row (via `slot_id`) — current
  behaviour, unchanged.
- **Open mode (B):** taken directly from the request; `slot_id` is null.

Because both modes resolve to the same `(start_time, duration_minutes)` on the
booking row and the overlap constraint keys on `(location, plan, date, window)`
— not on `slot_id` — slot-mode and open-mode bookings coexist and conflict
correctly. The mode is a current switch (not date-scheduled) that only affects
new bookings.

## Architecture & layering

No new layers. Changes flow through the existing seams:

```
routers (thin)  ->  services.booking (mode branch)  ->  models
                    services.catalog (open availability)
```

- **Model/migration:** `locations.booking_mode`; `bookings.slot_id` nullable.
- **Schemas:** booking create/preview accept EITHER `slot_id` OR
  (`start_time` + `duration_minutes`); validated against the location's mode.
- **Service:** one new resolution step decides the window source by mode; every
  downstream rule (time pipeline, overlap, duration pricing) is reused as-is.
- **Availability:** a new open-mode endpoint generates candidate starts; the
  existing slot availability endpoint is untouched.
- **Frontend:** location settings toggle; booking form + wizard branch on mode.

## Data model

### `locations.booking_mode`
| column | type | default | notes |
|---|---|---|---|
| `booking_mode` | `TEXT` + CHECK `in ('slot','open')` | `'slot'` | NOT NULL, server default |

Enforced with an explicit CHECK constraint `ck_locations_booking_mode`
(lowercase enum values, per structure.md).

### `bookings.slot_id` becomes nullable
- Drop NOT NULL on `bookings.slot_id`. FK (`fk_bookings_slot_id`) and its
  `ON DELETE RESTRICT` are unchanged.
- Slot mode: `slot_id` set (as today). Open mode: `slot_id` null.
- `start_time` / `duration_minutes` remain the authoritative window on the
  booking in BOTH modes (already NOT NULL post-0012), so the overlap
  exclusion constraint and `occupied_range` keep working for null-slot rows.

### Migration (0013)
- `ALTER TABLE locations ADD COLUMN booking_mode TEXT NOT NULL DEFAULT 'slot'`
  + `CHECK (booking_mode IN ('slot','open'))`.
- `ALTER TABLE bookings ALTER COLUMN slot_id DROP NOT NULL`.
- Additive + back-compatible: existing locations default to `slot`; existing
  bookings keep their `slot_id`. No data backfill required.

## Schema (Pydantic) changes

The booking request shape must accept either a slot or a raw window. Make the
window fields optional and validate the combination against the location's mode
in the service (the schema can only enforce structural rules; mode is a DB fact).

`PreviewBase` / `BookingCreate` (and thus `AdminPreviewRequest`,
`PublicPreviewRequest`, `AdminBookingCreate`):
- `slot_id: int | None = None` (was required int).
- add `start_time: time | None = None` (validator: minute ∈ {0,30}, sec 0).
- add `duration_minutes: int | None = None` (>0).

`BookingUpdate`:
- add `start_time: time | None` and `duration_minutes: int | None` so an
  open-mode booking's window can be edited; `slot_id` is not edited here.

Structural validator (schema level): reject a request that supplies BOTH
`slot_id` AND (`start_time`/`duration_minutes`) — ambiguous. The mode-match
check (slot-mode requires slot_id; open-mode requires start+duration) is done in
the service where the location's mode is known.

## Service design

### Window resolution (the one new branch)
Add a helper that both create and preview call, returning the authoritative
`(start_time, duration_minutes)` and the `slot_id` to persist:

```
resolve_booking_window(db, location, plan_id, *, slot_id, start_time,
                       duration_minutes, booking_date) -> WindowResolution
```

- Load `location.booking_mode`.
- **slot mode:** require `slot_id`; load+validate the slot (as today via
  `_load_valid_slot`); window = slot's `(start_time, duration_minutes)`;
  persisted `slot_id` = slot.id. Reject if start/duration were sent instead
  (mode mismatch → 422).
- **open mode:** require `start_time` + `duration_minutes`; validate :00/:30 and
  >0; window = those values; persisted `slot_id` = None. Reject if `slot_id` was
  sent (mode mismatch → 422). Require an active `plan_pricing` row for
  `(plan, duration)` on the date (so the duration is actually offered/priced).

Everything after resolution is unchanged and shared:
- `_enforce_booking_time(...)` (future-start, working-hours, end-before-close,
  same-day cutoff) with the actual actor.
- `_assert_no_overlap(...)` pre-check + the DB exclusion constraint backstop.
- `resolve_duration_pricing(plan, duration_minutes, date)` → base price +
  advance (R11), identical for both modes.

This replaces the current inline `_load_valid_slot` + `_slot_timing` calls in
`create_customer_booking`, `create_admin_booking`, `preview_booking`, and the
edit path, with `resolve_booking_window`. `validate_booking_request` keeps doing
item validation but no longer hard-requires a slot.

### Edit (`update_booking`)
- Slot-mode bookings: window is fixed by the existing slot (unchanged; slot/date
  not edited here today).
- Open-mode bookings: allow editing `start_time`/`duration_minutes`; when
  changed, re-resolve the window, re-run the time pipeline + overlap pre-check
  (with self-exclusion via `exclude_booking_id`), and re-price from the new
  duration. When unchanged, behave as today.

### `BookingRead` / mappers
- `slot_id` becomes `int | None` in the read schema. The slot-description label
  (`booking_plan_and_slot_labels`) already tolerates a missing slot; for open
  mode derive the label from `start_time`+`duration_minutes` (reuse
  `slot_label`-style formatting) so lists/WhatsApp show a time range.

## Open-mode availability

New service + endpoint (slot mode keeps using the existing
`available-slots`):

```
POST /api/v1/public/plans/{plan_id}/open-availability
body: { location_id, booking_date, duration_minutes }
-> [ { start_time, is_available } ]   # :00/:30 across working hours
```

- Generate candidate starts at :00/:30 from `opens_at` to the latest start whose
  usable end ≤ `closes_at` (respecting midnight crossover via the existing
  `working_window` helper).
- For each candidate, `is_available` = passes `validate_booking_time` for the
  actor AND its occupied window (incl. buffer) does not overlap any active
  booking for `(location, plan, date)` — reuse `_active_occupied_windows` +
  `occupied_window.overlaps`.
- Admin variant passes `ActorKind.ADMIN` (future/cutoff exemptions), mirroring
  how the current availability endpoint is actor-aware.
- Buffer never surfaced; only usable windows are presented.

An admin-scoped equivalent (or an `actor` derivation on the same handler) serves
the admin booking form, consistent with the existing availability endpoint's
public/admin handling.

## API surface

- `PATCH /api/v1/admin/locations/{id}` — accepts `booking_mode`
  (admin only; already admin-scoped). `LocationAdminRead` + `LocationRead` gain
  `booking_mode`.
- `POST /api/v1/public/plans/{id}/open-availability` — new (public allowlist),
  plus the admin path for staff/admin booking.
- `POST /public/bookings`, `POST /admin/bookings`, `PATCH /admin/bookings/{id}`,
  and both `.../preview` — bodies now accept the open-mode window fields; server
  validates against mode.

## Frontend design

- **Location settings (admin):** a `booking_mode` select (Slot / Open),
  admin-only, via the existing location update.
- **Booking form (admin) + customer wizard:** read the selected location's
  `booking_mode`.
  - slot mode → existing slot picker (unchanged).
  - open mode → a **Duration** selector (the plan's priced durations from
    `plan_pricing`) + a **Start time** picker populated from the open-availability
    query, greying out unavailable starts; show the duration base price and
    re-price the preview on duration/start change.
- Both modes surface the same rejection messages and never show the buffer.
- Preview/create payloads send either `slot_id` or `start_time`+`duration_minutes`
  by mode.

## Testing strategy (real Postgres for integration)

Reuse the existing harness. Mandatory (tech.md) + regression:
- Open-mode concurrent identical-window inserts → exactly one wins (DB
  exclusion constraint with null `slot_id`).
- Open-mode server pricing: duration drives base price; client base ignored;
  fallback when no `plan_pricing` row → request rejected (duration not offered).
- Open-mode validation: missing/invalid start+duration, non-:00/:30, mode
  mismatch both directions (422).
- Overlap + buffer parity: a slot-mode and an open-mode booking on the same
  (location, plan, date) with overlapping windows conflict.
- Time rules parity in open mode (working-hours, end-before-close, future-start,
  same-day cutoff) with role exemptions.
- `booking_mode` toggle: admin can set; staff 403.
- Migration: `booking_mode` default `slot`; `slot_id` nullable; existing rows
  intact.
- No regression: all existing slot-mode integration tests pass unchanged.
- Frontend (vitest): mode-driven rendering; open-mode duration re-pricing;
  disabled start selection; toggle admin-only.

## Trade-offs & decisions
- **Optional `slot_id` vs separate tables:** making `slot_id` nullable keeps one
  bookings table and reuses the overlap constraint unchanged — far simpler than a
  parallel slotless table, at the cost of a nullable FK (acceptable; the window
  columns remain the source of truth).
- **Mode validated in service, not only schema:** mode is a DB fact per location;
  the schema enforces structure (not both slot_id and window), the service
  enforces the mode match. Keeps routers thin.
- **Open durations limited to priced durations:** a duration must have an active
  `plan_pricing` row to be offered, so every open-mode booking has an
  authoritative base price (no implicit/unpriced durations). Matches R3.3.
- **Current switch, not date-scheduled:** per the requirements, avoids
  effective-dated mode rules; existing bookings are never rewritten.
