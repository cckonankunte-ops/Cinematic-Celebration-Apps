# Per-branch Booking Mode (slot vs open)

Each location (branch) has a `booking_mode` controlling how a booking's time
window is produced. It is an admin-toggled **current switch** (not
date-scheduled) that only affects NEW bookings from the moment it is flipped.

## The two modes

- **`slot` (default):** bookings reference a configured `Slot` row (`slot_id`);
  staff/customers pick from the plan's slots. This is the original behaviour and
  the default for every existing location.
- **`open`:** no per-start-time slot rows. The user picks a **duration** (the
  plan's priced durations from `plan_pricing`) and a **start time** (:00/:30)
  generated from the branch's working hours. The booking stores
  `start_time` + `duration_minutes` directly with `slot_id = NULL`.

Both modes resolve to the same underlying truth: a booking occupies
`[start, start + duration + cleaning_buffer)` on a date, validated by the shared
time-rule pipeline (future-start, working-hours, end-before-close, same-day late
cutoff) and the `excl_bookings_active_overlap` exclusion constraint, and priced
by duration via `plan_pricing`. Only the *source* of `(start, duration)` differs.

## Switching behaviour

- An admin may toggle `booking_mode` between `slot` and `open` at any time and
  any number of times (e.g. Mode A for a month, Mode B for a few days, back).
- Switching NEVER alters existing bookings. A booking made in `open` mode keeps
  its `start_time`/`duration_minutes` and null `slot_id` forever, even after the
  branch is switched back to `slot`.
- Slot-mode and open-mode bookings **coexist** on the same branch and conflict
  correctly: the overlap constraint keys on `(location, plan, date, window)`,
  not on `slot_id`.

## How the window is resolved (server)

`services/booking.resolve_booking_window(...)` is the single branch point used by
create (public + admin), preview, and edit:

- slot mode → requires a valid `slot_id`; window from the slot; persisted
  `slot_id = slot.id`. Sending start+duration instead → 422 (mode mismatch).
- open mode → requires `start_time` (:00/:30) + `duration_minutes`; window taken
  directly; persisted `slot_id = NULL`. Sending a `slot_id` → 422 (mode
  mismatch). The duration must have an active `plan_pricing` row (so every open
  booking has an authoritative base price); an unpriced duration → 422.

Everything after resolution (time pipeline, overlap pre-check + DB constraint,
duration pricing) is shared and unchanged.

## API

- `PATCH /api/v1/admin/locations/{id}` accepts `booking_mode` (admin only).
- `GET  /api/v1/public/plans/{id}/durations` — bookable durations + base price
  (open mode).
- `POST /api/v1/public/plans/{id}/open-availability` — candidate :00/:30 starts
  for a chosen duration, each flagged `is_available`.
- `POST /api/v1/admin/bookings/open-availability` — same, actor-aware (admin/
  staff exemptions).
- Booking create/preview/edit bodies accept EITHER `slot_id` OR
  `start_time` + `duration_minutes` (never both); the server validates against
  the location's mode.

## Data model

- `locations.booking_mode` — TEXT, CHECK `in ('slot','open')`, NOT NULL, default
  `'slot'`.
- `bookings.slot_id` — now **nullable** (null for open-mode bookings). FK and
  `ON DELETE RESTRICT` unchanged.
- Migration `0013_add_booking_mode_and_nullable_slot_id` — additive, no backfill.

## Sheets / reporting note

Time sheet and cake sheet now LEFT-join the slot and order by the booking's own
`start_time`, so open-mode bookings (null `slot_id`) appear correctly with a
derived time-range label.

## Operational steps after enabling open mode for a branch

1. Ensure the plan has `plan_pricing` rows for the durations you want to offer
   (e.g. 60 and 120 minutes) — these drive both the offered durations and the
   base price.
2. Set the branch's working hours (open/close) so the generated start times are
   correct.
3. Toggle the branch's booking mode to `open` in Catalog → Location settings.
