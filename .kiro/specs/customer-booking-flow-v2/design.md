# Design — Customer Booking Flow v2

## Overview

This design reworks the customer booking UX on the Astro site into a BingeTown-
style flow and adds two server-side capabilities that the flow depends on:

- **Kids pricing**: a per-plan `kid_price_pct` so children (3–10 yrs) are charged
  a whole-rupee fraction of the plan's *current* extra-guest rate.
- **Special-decor categories**: a `category` on each special-decor item so the
  Addons step groups items by Extra Decoration / Choose Gifts / Special Service.

It deliberately reuses the existing booking engine: window resolution
(`resolve_booking_window`), duration pricing (`plan_pricing`), coupons, the
double-booking guard, and the server-authoritative `pricing.py`. The customer
sends only IDs, quantities, and guest counts. No online payment is added
(Phase 1); the final step submits a `pending` booking request.

The work spans four layers, in dependency order:
1. **Schema**: `plans.kid_price_pct`, `special_decor_items.category` (+ migrations).
2. **Pricing + validation**: kids charge in `pricing.py`; adults/kids in requests.
3. **API schemas + catalog**: carry `kids` and decor `category`.
4. **Frontends**: admin fields; Astro home widget, branch screen, 5-step wizard,
   sticky summary, floating Call button.

## Steering alignment

- Money stays integer paise; all totals computed in `services/pricing.py`; client
  never sends money (tech.md "Pricing server-authoritative").
- Extra-guest and advance rules come from the DB (plan), never hardcoded; the kid
  percentage is a new DB-driven per-plan field (tech.md "Money/Pricing").
- Schema changes go through Alembic with explicit CHECK constraints and documented
  defaults (tech.md "Data", structure.md "Database").
- Layering preserved: routers thin, services own logic/transactions, models hold
  constraints, schemas separate from models (structure.md "Backend Layering").
- Frontend organized by feature, mobile-first, bundle kept small, TanStack Query on
  admin, runtime fetch on the static web site (tech.md "Frontend Rules").

## Data model changes

### 1. `plans.kid_price_pct`

New column on `plans`:

- `kid_price_pct SMALLINT NOT NULL DEFAULT 50`
- CHECK constraint `ck_plans_kid_price_pct_range`: `kid_price_pct BETWEEN 0 AND 100`.
- Documented default **50** (kids = half the adult extra-guest rate), matching the
  reference site and the owner's example (adult ₹150 → kid ₹75). Existing/migrated
  rows backfill to 50.

Model (`app/models/plan.py`):

```python
kid_price_pct: Mapped[int] = mapped_column(
    SmallInteger, nullable=False, server_default=text("50")
)
__table_args__ = (
    CheckConstraint(
        "kid_price_pct BETWEEN 0 AND 100", name="ck_plans_kid_price_pct_range"
    ),
)
```

### 2. `special_decor_items.category`

New column on `special_decor_items`:

- `category TEXT NOT NULL DEFAULT 'extra_decoration'`
- CHECK constraint `ck_special_decor_items_category`:
  `category IN ('extra_decoration', 'gifts', 'special_service')`.
- Stored values are lowercase snake_case (structure.md enum rule). Display labels
  map in the UI: `extra_decoration` → "Extra Decoration", `gifts` → "Choose Gifts",
  `special_service` → "Special Service".
- Existing rows backfill to `extra_decoration` (documented default).

Model (`app/models/special_decor_item.py`):

```python
SPECIAL_DECOR_CATEGORIES = ("extra_decoration", "gifts", "special_service")

category: Mapped[str] = mapped_column(
    String, nullable=False, server_default=text("'extra_decoration'")
)
__table_args__ = (
    CheckConstraint(
        "category IN ('extra_decoration', 'gifts', 'special_service')",
        name="ck_special_decor_items_category",
    ),
)
```

### Migrations (Alembic, two revisions on top of 0014)

- `0015_add_kid_price_pct_to_plans`: add column with `server_default='50'` and the
  range CHECK. Downgrade drops both.
- `0016_add_category_to_special_decor_items`: add column with
  `server_default='extra_decoration'` and the value CHECK. Downgrade drops both.

- `0017_add_kids_to_bookings`: add `kids SMALLINT NOT NULL DEFAULT 0` with CHECK
  `kids >= 0`. Downgrade drops both.
- `0018_create_location_disallowed_times`: create the table above with its FK and
  CHECK. Downgrade drops the table.

All are additive, backfill via `server_default`, and are safe on the populated
staging/production DB. Keeping `server_default` on each column means inserts that
omit the field stay valid (matches the existing pattern for `coupon_discount_paise`).

### 3. Disallowed booking time ranges per branch

New table `location_disallowed_times` (one row per blocked range per branch):

- `id` bigint PK
- `location_id` FK → `locations.id`, `ON DELETE CASCADE`, indexed
- `start_time TIME NOT NULL`, `end_time TIME NOT NULL`
- `max_duration_minutes SMALLINT NULL` — when set, the range only blocks bookings
  of that duration or shorter (e.g. "no 1-hour bookings after 22:00"); NULL blocks
  any booking overlapping the range
- `note TEXT NULL` (admin label), `is_active BOOLEAN NOT NULL DEFAULT true`
- CHECK `ck_location_disallowed_times_order`: `start_time < end_time`

Model in `app/models/location_disallowed_time.py`. Migration
`0018_create_location_disallowed_times`.

> A separate table (not JSON on `locations`) keeps real FKs and lets staff manage
> ranges individually, consistent with structure.md ("real foreign keys
> everywhere").

### Booking guest storage

Bookings currently store a single `people` int. We keep `people` as the **adult**
count (backward compatible: historical rows = adults) and add a nullable
`kids` count:

- `bookings.kids SMALLINT NOT NULL DEFAULT 0` (migration `0017_add_kids_to_bookings`,
  `server_default='0'`, CHECK `kids >= 0`).

This preserves every existing reader of `bookings.people` and the extra-guest
snapshot. Total guests = `people + kids`.

> Decision: we do NOT rename `people` to `adults`. Renaming would ripple through
> schemas, the admin list, analytics, and the migrator for no functional gain. We
> treat `people` as adults and add `kids` alongside.

## Pricing design (`services/pricing.py`)

### Guest-allowance + kid rule (the single documented rule)

Finalized from the requirements' proposed default:

1. Let `allowed = plan.people_allowed`, `adults = people`, `kids = kids`.
2. **Adults fill the allowance first.** `adult_extras = max(0, adults - allowed)`.
3. **Remaining allowance covers kids.** `allowance_left = max(0, allowed - adults)`;
   `kid_extras = max(0, kids - allowance_left)`.
4. `extra_guest_paise = adult_extras * plan.extra_guest_paise`
   `+ kid_extras * kid_rate_paise(plan)`.
5. Kids under 3 are neither counted nor charged (the UI simply doesn't collect
   them; nothing server-side needed).

This is a superset of today's behavior: when `kids == 0` it reduces exactly to the
current `_extra_guest_paise(plan, people)`, so all existing pricing tests still hold.

### Kid rate (whole-rupee, derived from current rate)

```python
def kid_rate_paise(plan: Plan) -> int:
    """Per-kid extra charge: kid_price_pct % of the plan's CURRENT extra-guest
    rate, rounded half-up to a whole RUPEE (multiple of 100 paise)."""
    raw = _round_half_up(plan.kid_price_pct * plan.extra_guest_paise, 100)  # paise, pct applied
    return _round_to_whole_rupee(raw)

def _round_to_whole_rupee(paise: int) -> int:
    """Round paise to the nearest whole rupee (100 paise), half-up."""
    return _round_half_up(paise, 100) * 100
```

Because the rate is computed from `plan.extra_guest_paise` at pricing time, raising
the adult rate later automatically raises the kid charge — no stored kid price.
Worked examples (kid_price_pct=50): extra ₹150 → 7500 paise → ₹75; extra ₹149
(14900 paise) → 50% = 7450 → round to whole rupee = 7500 = ₹75.

> Note on double-rounding: we apply the percentage then round to whole rupee in one
> helper so there is exactly one rounding step for the kid amount. The existing
> `_round_half_up` is reused for the percentage math; a thin `_round_to_whole_rupee`
> wraps the final whole-rupee step.

### `ValidatedRequest` + `compute_booking_price`

- `ValidatedRequest` gains `kids: int = 0`.
- `_extra_guest_paise(plan, people)` is replaced by
  `_extra_guest_paise(plan, adults, kids)` implementing the rule above; callers pass
  `req.people` (adults) and `req.kids`.
- `PriceBreakdown.extra_guest_paise` remains a single combined figure (adult + kid
  extras), so the booking snapshot and all readers are unchanged. The breakdown may
  optionally expose `kid_extra_guest_paise` for UI transparency (additive field,
  default 0) — included so the summary can show "Kids (n)" as its own line.

## Disallowed-times design

### Enforcement (`services/slots.py` + `services/booking.py`)

- A pure helper `is_time_disallowed(ranges, start, duration_minutes)` returns True
  when the booking's occupied window overlaps any active range whose
  `max_duration_minutes` is NULL or `>= duration_minutes`. Pure function → unit
  testable with no DB.
- Open-mode availability generation (`OpenAvailabilityRead`) marks a candidate
  start `is_available = False` when `is_time_disallowed` is True (customer view).
- `_enforce_booking_time` loads the branch's active ranges and, for a customer
  (`ActorKind.PUBLIC`), raises `ValidationFailedError` when the window is
  disallowed. Admins are subject to it too but may pass an explicit override flag
  (mirrors how late-booking/future-start exemptions already work for admins).
- Config is forward-looking: enforcement runs only at availability/creation time;
  nothing mutates existing bookings.

### Admin CRUD (`routers/admin` + `services/catalog_admin.py` or a small
`services/locations.py`)

- `GET/POST/DELETE /api/v1/admin/locations/{id}/disallowed-times` (admin-only via
  the existing router-level role dependency). Create validates `start < end` and a
  valid optional duration; returns the persisted range.
- Pydantic schemas `DisallowedTimeCreate` / `DisallowedTimeRead` in a schema module
  (e.g. `schemas/location_admin.py`).

### Validation (`services/booking.py`)

- `validate_booking_request` gains a `kids: int = 0` parameter.
- Guest cap check becomes: `total = people + kids`;
  reject when `total < 1` or `total > plan.max_people_allowed`
  (ValidationFailedError, 422). Adults must be ≥ 1 (a booking needs at least one
  adult); kids ≥ 0.
- `ValidatedRequest(... kids=kids)` is populated.

## API schema changes

### Requests (`app/schemas/booking.py`)

Add `kids` to the request shapes, keeping `people` as adults:

- `PreviewBase`: `kids: int = Field(default=0, ge=0)`.
- `BookingCreate`: `kids: int = Field(default=0, ge=0)`.
- `AdminBookingCreate` inherits it; `BookingUpdate` gains `kids: int | None`.
- `people` keeps `Field(ge=1)` (adults ≥ 1).

The service passes `kids` into `validate_booking_request`. Default 0 keeps every
existing client/test working unchanged.

### Breakdown response

- `PriceBreakdownRead` gains `kid_extra_guest_paise: int = 0` (additive, default 0)
  so the UI can render a kids line. `extra_guest_paise` stays the combined total.

### Booking read

- `BookingRead` and `BookingListItem` gain `kids: int = 0` (additive). The admin
  booking detail/edit can show and edit kids.

### Catalog reads (`app/schemas/catalog.py`)

- `PlanRead` gains `kid_price_pct: int`.
- `SpecialDecorRead` gains `category: str` (the stored lowercase value; the client
  maps to a display label).

### Admin catalog schemas (`app/schemas/catalog_admin.py`)

- Special-decor create/update schema gains `category: Literal[
  "extra_decoration", "gifts", "special_service"]` (validated; unknown → 422).
- Plan create/update schema gains `kid_price_pct: int = Field(ge=0, le=100)`.
- Plan admin schema also surfaces `advance_paise` (min advance) for editing
  (Requirement 6.6) — if it is not already editable, add it here.

## Public offers showcase design

A minimal, read-only showcase of already-existing coupon offers (the richer
scrolling banner is the separate `offers-headline-banner` spec).

- New public endpoint `GET /api/v1/public/offers` returning a list of safe fields
  only: `code`, `description` (a human blurb; reuse an existing coupon description
  field or a short derived label), and validity dates. It MUST NOT expose usage
  limits, per-customer redemption data, caps, or percentage-base internals.
- Service `coupon.py` gains `list_public_offers(db, *, on)` selecting active,
  currently-valid, customer-visible coupons. "Customer-visible" is gated by an
  existing active/validity flag; if a dedicated "showcase on home" flag is wanted,
  it is added in the `offers-headline-banner` spec, not here.
- Schema `PublicOfferRead` in `schemas/coupon.py`.
- The server stays authoritative: the showcase is informational; the real discount
  is still validated and computed at booking time.

## Service + router wiring

- `catalog.py` (public) includes `kid_price_pct` on plan reads and `category` on
  special-decor reads. No new endpoints; existing public catalog endpoints just
  return the extra fields.
- `catalog_admin.py` validates and persists `category` and `kid_price_pct`.
- `booking.py` preview + create pass `kids` through to validation/pricing.
- No change to routing, auth, rate limits, or the double-booking guard.

## Frontend design — Admin (`apps/admin`)

Feature folders already exist under `src/features/catalog/`.

- **Special-decor form**: add a Category select (3 options with display labels) to
  the create/edit form; send the lowercase enum value. Show the category in the
  decor list.
- **Plan form**: add a "Kids price %" number input (0–100, default 50) and ensure a
  "Minimum advance (₹)" input is present and bound to `advance_paise`. Mirror the
  API validation with zod (0–100 integer).
- **Disallowed times**: a small manager UI under the location/branch settings to
  list, add, and remove disallowed time ranges (start, end, optional max duration,
  note). Uses the new admin endpoints via TanStack Query mutations. Admin-only.

No new top-level routes beyond the branch-settings area; these extend existing
catalog/branch forms. TanStack Query mutations reuse
the existing catalog admin hooks.

## Frontend design — Customer site (`apps/web`)

### Routing model (unchanged constraint)

The site is a static build, so routing data stays in the URL/query. The booking
screen remains `/book?location=slug` and additionally reads `?date=YYYY-MM-DD`
(and optional `?plan=`). The home widget just builds that URL.

### New/changed components

```
src/layouts/Base.astro            # add floating Call button island (alongside WhatsApp)
src/pages/index.astro             # mount HomeBookingWidget + OffersShowcase islands in the hero
src/components/booking/
  HomeBookingWidget.tsx           # NEW: branch dropdown + date + Book Now + Call now
  OffersShowcase.tsx              # NEW: active-offers list on home (safe public fields)
  FloatingCall.tsx                # NEW: site-wide floating call button (branch picker)
  BranchBookingScreen.tsx         # NEW: top "Update" (branch+date) + plan/slot selection
  BookingWizard.tsx               # REWORK: 5 steps + skippable + sticky summary
  BookingSummary.tsx              # NEW: collapsible server-priced summary (Total/Advance/Balance)
  GuestCounter.tsx                # NEW: adults + kids steppers
  DecorByCategory.tsx             # NEW: groups special decor by category (vertical on mobile)
  OccasionPicker.tsx              # NEW/extracted: occasion tiles (skippable)
  CakePicker.tsx                  # NEW/extracted: cake + weight (skippable)
  types.ts                        # add adults/kids to BookingDraft
```

`SlotPicker` and `OpenSlotPicker` are reused unchanged (Requirement 3.3 keeps the
current time-selection behavior: slot mode picks a slot; open mode picks duration
then start window).

### Home booking widget (`HomeBookingWidget.tsx`)

- Fetches active locations at runtime; renders a Branch `<select>` (no City), a
  native date `<input type="date">` defaulting to `todayIsoInIST()` with `min` =
  today, a primary "Book Now", and a "Call now" button.
- "Book Now": if no branch chosen, show an inline prompt and don't navigate; else
  navigate to `/book?location={slug}&date={date}`.
- "Call now": `tel:` link to the selected branch's phone (or a default contact
  number from a branch when none selected).

### Branch booking screen (`BranchBookingScreen.tsx`)

- Reads `location` + `date` from the query string; fetches the branch, its plans,
  cakes, decor (with category), combos, occasions (same calls the current wizard
  makes).
- Top **Overview + Update** block: branch name, address, date; an "Update" control
  that lets the customer change **branch and date** in place (a compact branch
  `<select>` + date input); changing either refetches plans/availability.
- Lists the plan(s) with image, "₹X for up to N people", max-people text, and the
  time-window picker (`SlotPicker` or `OpenSlotPicker` by `booking_mode`).
- On choosing a plan + available window, proceeds into the wizard ("Add details,
  cakes, add-ons").

> Implementation choice: fold the branch screen and the wizard into one island
> mounted on `/book` so draft state (plan, window, guests, add-ons) is shared
> without serializing through the URL. The "screen vs wizard" split is internal
> view state, not separate pages.

### Five-step wizard (`BookingWizard.tsx` rework)

Steps and the progress indicator: **Basic Details → Occasion → Cake → Addons →
Payment**.

- **Basic Details**: Overview card (branch/location/date/time window), Booking Name
  (required, blocks Next when empty), `GuestCounter` (adults ≥ 1, kids ≥ 0),
  optional special-person name / name-on-cake.
- **Occasion**: `OccasionPicker` tiles; "Next" allowed with no selection (skippable);
  a "Skip" affordance is explicit.
- **Cake**: `CakePicker` (cake + half-kg weight) or skip.
- **Addons**: `DecorByCategory` (grouped) + combos (when `showCombos`); an explicit
  **"Add later after booking"** link proceeds with no add-ons.
- **Payment**: Terms & Conditions text + an "I agree" checkbox; advance payable; the
  submit action is disabled until the box is checked. Submitting calls the existing
  `publicApi.createBooking` and shows the existing success panel (advance, payment
  instructions, tracking token).

Guest counts flow into both the preview request and the create request as `people`
(adults) + `kids`.

### Offers showcase (`OffersShowcase.tsx`)

- Mounted in the home hero. Fetches `GET /public/offers` at runtime and renders
  active offers as compact cards/chips (code + short description + validity). Omits
  itself entirely when the list is empty (no layout shift). Money is display-only;
  no client-side discount math.

### Collapsible booking summary (`BookingSummary.tsx`)

- Driven entirely by the server preview (`publicApi.previewBooking`), keyed on the
  priced inputs (plan, window, date, adults, kids, cake, weight, decor, combos, led,
  coupon). The client computes **no** money.
- Collapsed (default): Total, Advance payable, and the primary action
  ("Next step" / "Submit request"). Expanded: plan price, extra-guest (with a Kids
  line when `kid_extra_guest_paise > 0`), each add-on line, Subtotal, coupon,
  Advance payable, and **Balance = Total − Advance payable** labeled "payable at the
  venue".
- Shown on every step from Basic Details onward; sticky at the bottom within thumb
  reach. Advance payable = plan `advance_paise` for the resolved duration (already
  returned by the create path; for preview the UI reads the plan's advance).
- Guest display (Requirement 5.7): the expanded summary and the Review step show
  "People (above 10 yrs): N" and "Kids (3–10 yrs): M", and a "Kids (M)" charge line
  when `kid_extra_guest_paise > 0` (from the breakdown field added above).
- Preview errors (e.g. invalid coupon) render inline and never block editing.

### Decor by category (`DecorByCategory.tsx`)

- Groups `catalog.specialDecor` by `category`, renders categories in a fixed order
  (Extra Decoration → Choose Gifts → Special Service), each as a labeled section
  stacked vertically (single column on mobile). Empty categories are omitted.

### Floating Call button (`FloatingCall.tsx`)

- Mirrors the existing floating WhatsApp button pattern in `Base.astro`: fixed
  position, fetches branches at runtime, shows a branch list on tap, and each branch
  is a `tel:` link to its stored phone. Branches without a phone are not shown.

### Advance mandatory seam (Phase 1 vs later)

The Payment step renders Terms + "Submit request" and does not require payment. The
submit handler is isolated so the later PhonePe spec can swap "Submit request" for a
"Pay ₹{advance} and book" action that first creates the pending booking, then opens
the gateway, without touching steps 1–4. The minimum advance already comes from the
plan (`advance_paise`); making payment mandatory is a later-phase switch.

## Error handling

- Invalid category / kid_price_pct on admin writes → 422 (Pydantic + DB CHECK).
- Guest total over `max_people_allowed` → 422 ValidationFailedError, no booking.
- Slot conflict on submit → 409 SlotUnavailableError; UI prompts to pick another
  slot/date (existing behavior).
- Preview failures surface inline in the summary; wizard navigation not blocked.
- DB CHECK constraints are the backstop for category and kid percentage ranges even
  if a bad value bypasses the API.

## Testing strategy

Server tests use real Postgres (tech.md). Property-friendly pure-pricing tests live
in `tests/unit`; integration tests in `tests/integration`.

### Pricing (unit, `tests/unit/test_pricing_kids.py`)
- K1 whole-rupee kid rate: `kid_rate_paise` is always a multiple of 100 paise for
  pct ∈ {0,50,100} and a range of extra-guest rates; worked examples ₹150/₹149 → ₹75.
- K2 monotonicity: increasing `plan.extra_guest_paise` never decreases the kid rate
  (property over random rates/pcts).
- K3 allowance rule: adults fill allowance first; kids consume leftover allowance;
  only the overflow of each is charged (table of cases).
- K4 pct bounds: 0 → kid charge 0; 100 → kid charged at full adult rate.
- K6 integer paise + client money ignored (reuse existing preview test guarantees).
- Regression: `kids=0` reproduces current `extra_guest_paise` exactly for existing
  cases.

### Validation (integration)
- K5 total guests > `max_people_allowed` → 422, no booking row created.
- adults = 0 → 422 (people ge=1).

### Category (integration + component)
- C1 migration adds column + CHECK; existing rows default `extra_decoration`;
  inserting an invalid category raises an IntegrityError.
- C2 admin create/edit with unknown category → 422.
- C3 public catalog returns `category`; `DecorByCategory` groups and omits empty
  categories (vitest component test with faked catalog).

### Summary + flow (component, vitest)
- S1 Balance = Total − Advance payable across drafts (faked preview values).
- S2 changing an add-on triggers a re-price via the preview endpoint (faked API);
  no client-side money math.
- Wizard: Booking Name required blocks Next; Occasion/Cake/Addons skippable;
  terms checkbox gates submit.

### Disallowed times (unit + integration)
- `is_time_disallowed` pure helper: overlap + duration-constraint truth table (unit).
- T1 open-mode start overlapping a range is unavailable; customer booking for it is
  rejected (422); outside-range window still bookable (integration).
- T2 admin create with `start >= end` → 422; DB CHECK is the backstop.
- T3 adding a range does not change existing bookings.

### Offers showcase (integration + component)
- O1 `GET /public/offers` returns only safe fields for active offers; inactive
  excluded; no usage-limit/redemption fields present in the response.
- O2 `OffersShowcase` omits cleanly when empty (vitest).

### Guests in review (component)
- G1 summary/review shows adults + kids and a kids charge line only when
  `kid_extra_guest_paise > 0`.

### Submission (integration, real Postgres)
- B1 valid draft with adults+kids creates exactly one pending booking; response has
  advance + instructions + token; `bookings.kids` persisted.
- B2 concurrent same-slot submission → exactly one wins, other 409 (reuses existing
  concurrency test).

## Rollout / compatibility notes

- All schema changes are additive with server defaults; safe to apply to the live
  staging/production DB via `alembic upgrade head`.
- `kids` defaults to 0 everywhere, so existing clients, the admin panel, analytics,
  and the MariaDB migrator keep working with no change (migrated bookings = adults,
  kids 0).
- `.env.example` unchanged (no new config). If a default contact number for the
  "Call now" button (when no branch selected) is desired as config, add
  `PUBLIC_DEFAULT_CALL_NUMBER` to web env + `.env.example`; otherwise derive from the
  first active branch.
