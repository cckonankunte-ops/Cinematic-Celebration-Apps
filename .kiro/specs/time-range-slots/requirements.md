# Requirements — Time-range Slots with Cleaning Buffer and Working Hours

## Introduction

Today a slot is a free-text label (`slots.description`, e.g. "9 AM - 12 PM") with
no machine-readable times. Double-booking is prevented only by a unique index on
`(location_id, plan_id, slot_id, booking_date)` for active bookings — the system
has no concept of two slots overlapping in clock time. This blocks mixing 1-hour
and 2-hour durations safely, prevents enforcing a cleaning gap, and can't stop a
customer booking outside staffed hours.

This feature replaces label-only slots with **time-range slots**: each slot has a
`start_time` and a `duration_minutes`. Conflict detection moves from "same slot
id" to "**overlapping time window**", where a booking occupies
`[start, start + duration + cleaning_buffer)`. Working hours and a late-booking
cutoff are configured per location so customers can't book after staff have left.

Money, pricing, and the booking lifecycle are unchanged. This spec is about
*when* a slot runs and *whether* it can be booked, not *what it costs*.

### Current behaviour (confirmed)
- Staff currently select the old fixed 2-hour slot and write a note like
  "1 hour" for their own understanding. There is **no real overlap in live data
  yet**, which de-risks the retrofit (Requirement 8).
- Shops open 10:00 and close 01:00 next day (crosses midnight).
- Standard cleaning/preparation gap between bookings is 30 minutes.
- Allowed start times are on the hour or half-hour only (e.g. 3:00 PM, 3:30 PM),
  never :15/:45.

### Out of scope
- Changing pricing, plans, add-ons, coupons, payments, or the pending/accept
  lifecycle.
- Per-room physical inventory beyond what already exists (a plan is the room).
  Overlap is evaluated per `(location, plan, date)` — same basis as today's index.
- Recurring-schedule generators / templated weekly calendars (future phase).

---

## Glossary

- **Slot**: a bookable time window for a plan: `start_time` + `duration_minutes`.
- **Occupied window**: the clock range a booking blocks =
  `[start, start + duration_minutes + cleaning_buffer_minutes)`.
- **Cleaning buffer**: minutes reserved after a booking's usable time for
  cleaning/prep. Configurable; default 30. Invisible to the customer's displayed
  time; used only for conflict math.
- **Working window**: a location's bookable clock range (e.g. 10:00–01:00),
  which may cross midnight.
- **Late-booking cutoff**: the latest start time a customer may self-book online
  for a location; a switch allows booking past it.

---

## Requirements

### Requirement 1 — Slots carry real times

**User Story:** As an admin, I want each slot defined by a start time and a
duration, so the system knows exactly when a slot runs and can reason about
overlaps and durations of any length.

#### Acceptance Criteria
1. WHEN an admin creates a slot THEN the system SHALL require a `start_time`
   (local IST wall-clock, no date) and a `duration_minutes` (positive integer).
2. THE system SHALL compute a slot's end time as `start_time + duration_minutes`
   and SHALL NOT store a separate end column.
3. THE system SHALL retain a human-readable `description`; WHEN not provided by
   the admin THEN it SHALL be derived from start+duration (e.g. "3:00 PM –
   4:00 PM").
4. WHERE a slot's computed end crosses midnight (e.g. 11:30 PM + 120 min) THE
   system SHALL represent the window correctly for conflict math (Requirement 4).
5. THE slot continues to belong to exactly one plan and keeps `show_combos`,
   `sort_order`, validity (`effective_from`/`effective_to`), and `is_active`.

**Test cases**
- Create slot start 15:00 duration 60 → end 16:00, description auto "3:00 PM – 4:00 PM".
- Create slot start 23:30 duration 120 → end 01:30 next day (crosses midnight).
- Custom description overrides the derived one.

### Requirement 2 — Start times restricted to :00 / :30

**User Story:** As an admin, I want start times limited to the hour and
half-hour, so the schedule stays clean and predictable.

#### Acceptance Criteria
1. WHEN a slot's `start_time` is submitted THEN the system SHALL reject it with
   422 UNLESS its minute is `00` or `30` and its seconds are `00`.
2. THE database SHALL enforce the same rule with a CHECK constraint so invalid
   times cannot be inserted outside the application.
3. `duration_minutes` SHALL NOT be restricted to :00/:30 multiples beyond being a
   positive integer (so 60, 90, 120, 45 … are all allowed).

**Test cases**
- start 15:00 accepted; 15:30 accepted; 15:15 → 422; 15:45 → 422; 15:00:30 → 422.
- duration 90 accepted.

### Requirement 3 — Cleaning buffer reserved after each booking

**User Story:** As an operator, I want an automatic gap after every booking for
cleaning and setup, so two bookings never run back-to-back without turnaround.

#### Acceptance Criteria
1. THE cleaning buffer SHALL be a configurable value (default 30 minutes), read
   from settings/config and never hardcoded in logic.
2. THE system SHALL treat a booking's occupied window as
   `[start, start + duration_minutes + cleaning_buffer_minutes)`.
3. THE customer-facing displayed time SHALL show only the usable window
   (`start`..`start+duration`); the buffer SHALL NOT appear in the shown time.
4. WHERE two candidate bookings are exactly back-to-back at the buffer boundary
   (one's occupied end equals the other's start) THEN both SHALL be allowed.

**Test cases**
- Buffer 30; booking A 15:00–16:00 occupies 15:00–16:30; B starting 16:00 →
  rejected; B starting 16:30 → allowed.
- Displayed time for A is "3:00 PM – 4:00 PM" (no 4:30).

### Requirement 4 — Overlap-based conflict prevention (DB-enforced)

**User Story:** As the business, I want the database to guarantee no two active
bookings for the same plan/date occupy overlapping clock time, so a 1-hour and a
2-hour booking can never double-book the same room.

#### Acceptance Criteria
1. WHEN a booking is created or edited THEN the system SHALL reject it with 409
   "Slot not available" IF its occupied window overlaps any active
   (pending|accepted) booking's occupied window for the same
   `(location_id, plan_id, booking_date)`.
2. THE database SHALL enforce this with an exclusion constraint (range-aware,
   e.g. `btree_gist` over the occupied range) so overlaps are impossible even
   under concurrent requests — the range-aware successor to
   `uq_bookings_active_slot`.
3. Only `pending` and `accepted` bookings SHALL hold a window; `rejected` and
   `expired` SHALL NOT.
4. WHERE a booking's window crosses midnight THE overlap check SHALL remain
   correct (it is anchored to `booking_date` + the window).
5. THE concurrent-booking test (exactly one of two racing requests wins) from
   `tech.md` SHALL hold under the new range model.

**Test cases**
- Two overlapping windows same plan/date → second gets 409.
- Overlapping 1h and 2h on the same plan/date → one wins.
- Non-overlapping (after buffer) → both succeed.
- Two concurrent requests for the same window → exactly one wins (DB constraint).
- rejected/expired booking's window does not block a new booking.

### Requirement 5 — Per-location working hours

**User Story:** As an admin, I want to set each branch's open and close times, so
slots and bookings are constrained to hours we actually operate.

#### Acceptance Criteria
1. Each location SHALL have a working window (`opens_at`, `closes_at` local IST
   times) that MAY cross midnight (e.g. opens 10:00, closes 01:00).
2. WHEN a slot is created/edited THEN the system SHALL reject (422) any slot
   whose usable window falls outside its location's working window.
3. THE working window SHALL be stored per location (admin-tunable data, not an
   env var).
4. WHERE `closes_at < opens_at` THE system SHALL interpret the close time as the
   following day.
5. A booking's **usable end** (`start + duration_minutes`, excluding the cleaning
   buffer) SHALL NOT exceed the location's `closes_at`. WHEN a chosen start +
   duration would end after close (e.g. 12:00 AM start + 2h = 2:00 AM when close
   is 1:00 AM) THEN the system SHALL reject it (customer/staff) with a clear,
   meaningful message (e.g. "This booking would end after we close at 1:00 AM.
   Please choose a shorter duration or an earlier start.").
6. THE cleaning buffer MAY extend past `closes_at` (cleaning after the last
   booking is an internal activity); only the **usable end** is bound by close.

**Test cases**
- Location opens 10:00 closes 01:00; slot 23:30–00:30 accepted; slot 02:00–03:00 → 422.
- Location opens 10:00 closes 22:00; slot 22:30 start → 422.
- Close 01:00; start 00:00 duration 120 (ends 02:00) → rejected with the
  end-after-close message; start 00:00 duration 60 (ends 01:00) → accepted.
- Close 01:00, buffer 30; start 00:00 duration 60 ends 01:00, buffer to 01:30 is
  allowed (buffer may exceed close).

### Requirement 6 — Late-booking cutoff with override switch

**User Story:** As an operator, I want customer online bookings blocked after a
cutoff unless I switch late booking on, so no one books 11 PM/12 AM when staff
have gone home.

#### Acceptance Criteria
1. Each location SHALL have a `last_online_booking_start` cutoff time and an
   `allow_late_booking` switch (boolean).
2. WHEN a customer (public) requests a slot whose start is at/after the cutoff
   AND `allow_late_booking` is false THEN the system SHALL NOT offer that slot and
   SHALL reject a direct booking attempt with a clear error.
3. WHERE `allow_late_booking` is true THEN slots whose **usable end** is at/before
   the location's close time SHALL be bookable; a late slot that would end after
   close is still rejected per Requirement 5.5 (the switch enables late *starts*,
   it does not waive the end-before-close rule).
4. Staff/admin creating a booking in the admin panel SHALL NOT be blocked by the
   cutoff (they can always book late on a customer's behalf); the cutoff applies
   to public self-service only. The end-before-close rule (5.5) STILL applies to
   staff; only an admin may override it (see Requirement 10).
5. THE cutoff and switch SHALL be per location and admin-tunable.

**Test cases**
- Cutoff 22:00, switch off: public availability hides 22:00+ slots; direct POST to
  a 22:30 slot → rejected.
- Cutoff 22:00, switch on: public can book a 23:00 slot.
- Admin can create a 23:00 booking regardless of the switch.

### Requirement 7 — Availability and booking UIs reflect time windows

**User Story:** As a customer and as staff, I want the booking screens to show
real slot times and correct availability, so I pick a valid, free slot.

#### Acceptance Criteria
1. THE availability endpoint SHALL return, for a plan/location/date, each slot
   with its usable start/end and an `is_available` flag computed from the overlap
   + buffer + working-hours + late-cutoff rules.
2. Booked/greyed slots SHALL remain visible but non-selectable (consistent with
   the existing greyed-slot behaviour).
3. THE admin booking form and the customer web wizard SHALL display slot times
   derived from start+duration (not a free-text label alone).
4. THE displayed time SHALL never include the cleaning buffer.

**Test cases**
- Availability marks a slot unavailable when its window overlaps a held booking
  (incl. buffer).
- Availability hides/greys post-cutoff slots for public when the switch is off.

### Requirement 8 — Retrofit existing slots and bookings

**User Story:** As the business, I want our existing slots and bookings migrated
to the new time model without data loss or invented times, so history stays
correct and the new overlap rule can be enforced safely.

#### Acceptance Criteria
1. THE migration SHALL add the new columns as nullable first (additive, safe),
   backfill, verify, and only then add NOT NULL / CHECK / exclusion constraints.
2. A one-off backfill script SHALL parse each existing slot `description` into
   `start_time` + `duration_minutes`.
3. WHERE a description cannot be parsed with confidence THE script SHALL write it
   to a report for manual mapping and SHALL NOT guess a time.
4. Each existing booking SHALL get its occupied window from a snapshot of its
   slot's parsed `start_time`/`duration_minutes` (snapshotted onto the booking,
   consistent with how prices and add-on names are already snapshotted), so later
   slot edits do not shift historical bookings.
5. BEFORE enabling the exclusion constraint THE migration SHALL verify no
   existing active bookings already overlap under the new window math; IF any
   overlap is found THE migration SHALL surface them for human resolution rather
   than silently enforcing.
6. THE retrofit SHALL run against real PostgreSQL (not SQLite), consistent with
   the testing rules.

**Test cases**
- "9 AM - 12 PM" → start 09:00, duration 180.
- "6:30 PM - 7:30 PM" → start 18:30, duration 60.
- An unparseable description is reported, not guessed.
- Post-backfill, every active slot has start+duration or is flagged.
- Overlap pre-check surfaces any existing clashing active bookings.

### Requirement 10 — Start must be in the future (admin may book in the past)

**User Story:** As the business, I want customers and staff to only book slots
starting in the future, while admins can record past bookings (e.g. backfilling a
walk-in), so online bookings are always serviceable but admins keep full control.

#### Acceptance Criteria
1. WHEN a customer (public) or a staff user creates a booking THEN the system
   SHALL reject it IF the slot's start (on the chosen `booking_date`, IST) is at
   or before the current time.
2. WHERE the actor is an admin THEN the system SHALL allow a start time in the
   past (no future-time restriction for admins).
3. THE "current time" comparison SHALL use IST (Asia/Kolkata), consistent with
   how booking dates are interpreted, and SHALL account for slots whose date is
   today (compare against the clock) vs. a future date (always allowed).
4. THE public availability endpoint SHALL NOT offer past-start slots for today.
5. This future-start rule is independent of the late-booking cutoff (Req 6) and
   the end-before-close rule (Req 5.5); all applicable rules are enforced.

**Test cases**
- Today, current time 14:00: public/staff booking a 13:00 slot → rejected;
  a 15:00 slot → allowed (subject to availability).
- Admin booking a 13:00 slot today → allowed (past-time override).
- Future date: any valid slot allowed for all roles (subject to other rules).
- Public availability for today hides slots whose start already passed.

### Requirement 11 — Base price varies by plan AND duration

**User Story:** As the business, I want the plan's base price (and advance, and
people allowance) to depend on the slot's duration, so a 1-hour booking and a
2-hour booking of the same plan charge different prices.

Examples (illustrative, real values are data):
- Plan 1, 1 hour → ₹799 (2 people, free entry)
- Plan 1, 2 hour → ₹1199 (2 people)
- Plan 2, 1 hour → ₹1499 (6 people)
- Plan 2, 2 hour → ₹1999 (6 people)

#### Acceptance Criteria
1. THE base price charged SHALL be determined by the selected `(plan, duration)`
   — i.e. by the chosen **slot** — not by the plan alone.
2. Server-side pricing (`services/pricing.py`) SHALL read the base price (and
   advance) from the duration-specific source for the selected slot, not from a
   single plan-level price, and SHALL remain server-authoritative (client sends
   only ids/quantities; client totals ignored).
3. WHERE a plan offers multiple durations THE system SHALL store a distinct base
   price (and advance) per duration.
4. People allowance (`people_allowed`, `max_people_allowed`) and the extra-guest
   charge do NOT vary by duration and SHALL remain plan-level attributes (they
   apply to all durations of the plan).
5. THE admin catalog SHALL let an admin set the base price (and advance) for each
   duration of a plan.
6. THE customer web and admin booking UIs SHALL show the price for the selected
   duration, and the live preview/total SHALL reflect the duration-specific base.
7. Money stays integer paise; all existing pricing rules (extra-guest, cake,
   decor, combos, LED, discount, coupon) apply on top of the duration-specific
   base unchanged.

**Test cases**
- Plan 1 + 1h slot prices at ₹799 base; Plan 1 + 2h slot at ₹1199; selecting the
  other duration re-prices the preview.
- Extra-guest / add-ons compute on top of the correct duration base.
- Client-sent base price is ignored; server uses the slot's duration price.
- Retrofit: existing (single-duration) plans keep their current price as the
  2-hour price (see Requirement 8 / design).

### Requirement 9 — Configuration and defaults

**User Story:** As an operator, I want the buffer, working hours, and cutoff to be
configurable, so we can adjust operations without a code change.

#### Acceptance Criteria
1. `CLEANING_BUFFER_MINUTES` SHALL be a setting with a default of 30 (env default;
   may later be overridable per location — design decision in design.md).
2. Working hours, late-booking cutoff, and the late-booking switch SHALL be
   per-location, admin-editable data.
3. `.env.example` and docs SHALL be updated for any new configuration variable.

---

## Mandatory test cases (money/integrity/access — per tech.md)

Although this feature does not change money, it changes **booking integrity**, so
the following MUST be covered:
- Concurrent booking of overlapping windows for the same plan/date: exactly one
  wins (DB exclusion constraint).
- Overlap rejection incl. the cleaning buffer; back-to-back at the buffer
  boundary allowed.
- Start-time :00/:30 validation (app + DB CHECK).
- Working-hours boundary rejection (incl. midnight crossover).
- Late-booking cutoff: public blocked when switch off, allowed when on; admin
  never blocked (access/role distinction).
- End-before-close: a late start whose duration would end after the close time is
  rejected for customer/staff with a meaningful message; buffer may exceed close.
- Future-start rule: customer/staff cannot book a start at/before now (IST);
  admin can book a past start (role distinction).
- Retrofit: known descriptions parse correctly; unparseable ones reported;
  existing-overlap pre-check.
