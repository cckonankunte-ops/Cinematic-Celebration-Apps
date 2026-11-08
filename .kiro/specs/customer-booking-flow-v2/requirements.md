# Requirements — Customer Booking Flow v2

## Introduction

Rework the customer-facing booking experience on the Astro site (`apps/web`) to
a BingeTown-style flow: a home-page booking widget (branch + date), a branch/
time-slot selection screen, and a 5-step wizard (Basic Details → Occasion →
Cake → Addons → Payment) with a persistent, server-authoritative booking
summary on every step.

Two supporting capabilities are added to make this flow correct:

1. **Kids pricing** — a per-plan configurable kids percentage so children
   (3–10 yrs) are charged a fraction of the adult extra-guest rate, derived from
   the current rate at booking time (not a frozen kid price).
2. **Special-decor categories** — a category on each special-decor item
   (Extra Decoration / Choose Gifts / Special Service) so the Addons step groups
   items by category, stacked vertically on mobile.

This spec covers only Phase-1 behavior: a booking is a **request** that holds the
slot as `pending`; staff record the advance and accept. There is **no online
payment** in this phase — the final step shows Terms & Conditions, the advance
payable, and a "Submit request" action. The real "Pay and book" button is
deferred to the separate PhonePe spec. When that lands, advance payment becomes
mandatory and the minimum advance is read from the plan's `advance_paise` (admin-
configurable).

Money stays integer paise end-to-end; all totals are computed on the server in
`services/pricing.py`. The client sends only IDs, quantities, and counts — never
money or totals.

### Scope

In scope:
- Home-page booking widget (branch dropdown + date + "Book Now"), plus a
  floating "Call now" action button alongside the existing floating WhatsApp
  button, shown site-wide.
- Branch/time-slot selection screen presentation (adapt to existing slot/open
  booking modes already in the system).
- 5-step customer wizard with skippable Occasion / Cake / Addons steps.
- Persistent collapsible booking summary (Total, line items, Subtotal, Advance
  payable, Balance payable at venue) on every step, from Basic Details onward.
- Kids/adults guest split with a per-plan kids percentage, priced server-side.
- Special-decor category field + admin editing + category-grouped Addons display.
- Admin-configurable disallowed booking time ranges per branch.
- Minimal home-page showcase of active coupon offers (safe public fields).
- Guest count (adults + kids) shown in the summary/review.

Out of scope (explicitly deferred):
- LED pricing for numeric characters — tracked as a separate bugfix spec
  (`led-number-pricing`): the current LED charge counts letters only, so digits
  in an LED name are not charged. Fixed independently of this feature.
- Scrolling headline / offers banner and its admin CRUD — tracked as a separate
  feature spec (`offers-headline-banner`). Requirement 11 here is only the minimal
  home-page showcase of existing coupon offers.
- Online payment / PhonePe integration and mandatory-advance enforcement.
- Customer self-service "add later" editing — in Phase 1 "add later" simply means
  the customer skips the step and staff follow up manually.
- City selection (Bangalore-only).
- Kids-below-3 handling beyond "not chargeable" display text.

## Requirements

### Requirement 1 — Home-page booking widget

**User Story:** As a customer landing on the home page, I want to pick a branch
and a date and start booking in one tap, so that I reach the right branch's
slots immediately.

#### Acceptance Criteria

1. WHEN the home page loads THEN the system SHALL display a booking widget on the
   hero containing a Branch dropdown (active branches only), a Date picker, a
   "Book Now" primary action, and a "Call now" action.
2. WHEN the page loads THEN the Branch dropdown SHALL be populated at runtime
   from the active-locations API (no City selector).
3. WHEN the Date picker is shown THEN it SHALL default to today (Asia/Kolkata)
   and SHALL NOT allow selecting a past date.
4. WHEN the customer selects a branch and date and taps "Book Now" THEN the
   system SHALL navigate to the branch booking screen for that branch and date
   (carried in the URL, consistent with the static-site routing already used by
   `/book?location=slug`).
5. IF the customer taps "Book Now" without selecting a branch THEN the system
   SHALL prompt the customer to choose a branch and SHALL NOT navigate.
6. WHEN the customer taps "Call now" THEN the system SHALL initiate a phone call
   to the branch's phone number (the selected branch, or a default contact
   number when no branch is selected).

### Requirement 2 — Site-wide floating Call button

**User Story:** As a customer on any page, I want a persistent call button like
the WhatsApp button, so that I can reach the venue quickly.

#### Acceptance Criteria

1. WHEN any customer page is shown THEN the system SHALL display a floating
   "Call" action button, visually consistent with the existing floating WhatsApp
   button, fixed in the viewport.
2. WHEN the customer taps the floating Call button THEN the system SHALL present
   the branch list (same pattern as the WhatsApp button) and, on selecting a
   branch, SHALL initiate a call to that branch's stored phone number.
3. WHEN a branch has no phone number THEN that branch SHALL NOT offer a call
   action.

### Requirement 3 — Branch / time-slot selection screen

**User Story:** As a customer, after choosing a branch and date, I want to see
the branch details and the available time slots with prices, so that I can pick a
slot and proceed.

#### Acceptance Criteria

1. WHEN the branch booking screen loads for a branch + date THEN the system SHALL
   display, at the top, the branch name, location/address, the chosen date, and an
   "Update" affordance that lets the customer change BOTH the branch and the date
   without going back to the home page; changing either SHALL reload the branch's
   plans and availability for the new selection.
2. WHEN the screen loads THEN the system SHALL display the branch's plan(s) with
   image, price "for up to N people", and max-people text.
3. WHEN a plan is shown THEN the system SHALL display its available time windows
   for the chosen date, marking already-booked windows as unavailable, using the
   branch's existing booking mode with NO change to current time-selection
   behaviour: in fixed-slot mode the customer picks a predefined slot; in open
   mode the customer first chooses a duration (e.g. 1 hour / 2 hours) and then
   picks an available start window, exactly as today.
4. WHEN the customer selects an available time window THEN the system SHALL
   enable proceeding to the wizard ("Add details, cakes, add-ons").
5. WHEN all windows for the date are unavailable THEN the system SHALL tell the
   customer to pick another date.
6. WHERE a branch has configured one or more disallowed time ranges (Requirement
   10) THEN the system SHALL NOT offer booking windows whose occupied time falls
   within a disallowed range for a customer, treating them like unavailable.

### Requirement 10 — Admin-configurable disallowed booking times per branch

**User Story:** As the owner, I want to block certain times at a branch (e.g. no
1-hour late-night slot), so that customers cannot book windows we don't operate.

#### Acceptance Criteria

1. WHERE a branch exists THEN the system SHALL let an admin configure zero or more
   disallowed time ranges for that branch, each a start–end wall-clock range
   (Asia/Kolkata), optionally constrained by duration (e.g. disallow 1-hour
   bookings after 22:00).
2. WHEN the admin saves a disallowed range THEN the system SHALL validate the
   range (start before end, valid times) and persist it with a real FK to the
   branch and documented ON DELETE behavior.
3. WHEN a customer requests available windows (open mode) OR selects a slot THEN
   the server SHALL exclude/forbid any window whose occupied time overlaps a
   disallowed range for that branch, returning the window as unavailable (open
   mode) or rejecting the booking with a validation error (both modes).
4. WHERE the actor is an admin creating a booking THEN the system SHALL still
   enforce disallowed ranges unless an explicit admin override is provided
   (consistent with how other time rules treat admins).
5. WHEN disallowed ranges change THEN existing bookings SHALL NOT be altered
   (config is forward-looking only).

### Requirement 11 — Showcase active offers on the home page

**User Story:** As a customer on the home page, I want to see current offers/
discount codes, so that I know I can save and how.

#### Acceptance Criteria

1. WHEN the home page loads THEN the system SHALL display the currently active,
   customer-visible offers (e.g. coupon code + short description) fetched at
   runtime from a public endpoint.
2. WHERE an offer is a coupon THEN the showcase SHALL show only safe, public
   fields (code, human description, and validity), never internal usage limits or
   per-customer data.
3. WHEN there are no active offers THEN the system SHALL omit the showcase without
   layout breakage.
4. WHEN an offer is shown THEN any monetary value SHALL be formatted for display
   only; the client SHALL NOT compute discounts (the server remains authoritative
   at booking time).

> Note: the richer scrolling headline/offers banner and its admin management are a
> SEPARATE feature spec (`offers-headline-banner`). Requirement 11 is the minimal
> home-page showcase of already-existing coupon offers, using safe public fields.

### Requirement 4 — Five-step booking wizard with skippable steps

**User Story:** As a customer, I want a clear step-by-step flow with a progress
indicator, so that I know where I am and can skip steps I don't need.

#### Acceptance Criteria

1. WHEN the wizard is shown THEN the system SHALL present five steps in order:
   Basic Details → Occasion → Cake → Addons → Payment, with a progress indicator
   marking completed, current, and upcoming steps.
2. WHEN on the Basic Details step THEN the system SHALL show an Overview card
   (branch, location, date, time window) and SHALL collect the Booking Name
   (required), guest counts (Requirement 6), and optional special-person/name-on-
   cake details.
3. WHEN the Booking Name is empty THEN the system SHALL block proceeding past
   Basic Details and SHALL show a "required" validation message.
4. WHEN on the Occasion step THEN the system SHALL display the branch's occasions
   as selectable tiles AND SHALL allow proceeding without a selection (skippable).
5. WHEN on the Cake step THEN the system SHALL allow choosing a cake and weight OR
   skipping (skippable), consistent with existing cake pricing (weight in half-kg
   units).
6. WHEN on the Addons step THEN the system SHALL display special decor grouped by
   category (Requirement 7) and combos (when the slot allows combos) AND SHALL
   provide an explicit "Add later after booking" skip that proceeds without any
   add-on selection.
7. WHEN on the Payment step THEN the system SHALL display Terms & Conditions and
   the advance payable and SHALL require agreement to the terms before enabling
   "Submit request" (Requirement 8).
8. WHEN the customer uses "Back" THEN the system SHALL return to the previous step
   preserving all entered data.
9. WHEN any step changes a priced input THEN the booking summary (Requirement 5)
   SHALL update from the server preview.

### Requirement 5 — Persistent server-authoritative booking summary

**User Story:** As a customer, I want to see a running price breakdown at every
step, so that I always know the total, the advance, and what's payable at the
venue.

#### Acceptance Criteria

1. WHEN the draft is priceable (plan + time window chosen) THEN the system SHALL
   display a booking summary on every step from Basic Details onward.
2. WHEN the summary is shown THEN it SHALL be collapsible: collapsed shows Total
   and Advance payable and the primary action ("Next step" / "Submit request");
   expanded shows line items, Subtotal, Advance payable, and Balance amount
   (payable at the venue).
3. WHEN any priced input changes THEN the system SHALL refresh the summary from
   the server pricing preview and SHALL NOT compute any money on the client.
4. WHEN the server preview fails (e.g. invalid coupon) THEN the system SHALL show
   the error inline without blocking the customer from editing inputs.
5. WHEN the summary shows Balance amount THEN Balance SHALL equal Total minus
   Advance payable, and the system SHALL label it "payable at the venue".
6. WHERE any amount is displayed THEN it SHALL be formatted in rupees for display
   only, derived from paise returned by the server.
7. WHEN the summary or Review is shown THEN it SHALL display the number of guests,
   split as adults (above 10 yrs) and kids (3–10 yrs), AND SHALL show the kids
   extra-guest charge as its own line when it is greater than zero.

### Requirement 6 — Kids / adults guest split with per-plan kids percentage

**User Story:** As the owner, I want to charge children a configurable percentage
of the adult extra-guest rate, computed from the current rate, so that raising the
adult rate later automatically updates kid pricing.

#### Acceptance Criteria

1. WHEN the Basic Details step is shown THEN the system SHALL provide separate
   counters for "People (above 10 yrs)" (adults) and "Kids (3–10 yrs)", each
   defaulting sensibly (adults ≥ 1, kids ≥ 0).
2. WHERE a plan is configured THEN the system SHALL store a per-plan kids
   percentage (integer 0–100) that is admin-editable; new/migrated plans SHALL
   default to a documented value.
3. WHEN pricing a booking THEN the server SHALL compute the kid charge per kid as
   the configured percentage of the plan's current extra-guest rate, so a later
   change to the extra-guest rate changes kid pricing automatically.
3a. WHEN the kid charge is computed THEN it SHALL be rounded to a whole rupee
   (whole hundreds of paise), half-up, so the displayed and charged kid amount is
   always a whole-rupee value with no fractional rupee or stray paise.
4. WHEN counting guests against the plan allowance THEN the system SHALL define
   which guests count toward `people_allowed` and which are charged as extras in a
   single documented rule in `services/pricing.py`, and the extra-guest and kid
   charges SHALL be computed consistently with that rule.
5. WHEN the total guest count (adults + kids) exceeds the plan's
   `max_people_allowed` THEN the system SHALL reject the request with a validation
   error and SHALL NOT create a booking.
6. WHEN the admin edits a plan THEN the system SHALL expose and persist the kids
   percentage and the minimum advance (`advance_paise`) fields.
7. WHEN kids pricing is computed THEN all amounts SHALL be integer paise and the
   client SHALL send only counts, never money.

### Requirement 7 — Special-decor categories

**User Story:** As the owner, I want to categorize special-decor items (Extra
Decoration / Choose Gifts / Special Service), so that customers see them grouped
by category on the Addons step.

#### Acceptance Criteria

1. WHERE a special-decor item exists THEN the system SHALL store a category on it,
   constrained to a fixed set of values with a database CHECK constraint: Extra
   Decoration, Choose Gifts, Special Service.
2. WHEN the schema changes THEN an Alembic migration SHALL add the category column
   with the CHECK constraint and a documented default for existing rows.
3. WHEN the admin creates or edits a special-decor item THEN the system SHALL let
   the admin set its category, and the create/edit API SHALL validate the category
   value.
4. WHEN the Addons step renders special decor THEN the system SHALL group items by
   category, rendering categories one below another (vertical stack) on mobile,
   with a heading per category.
5. WHEN a category has no active items THEN the system SHALL omit that category
   heading.
6. WHEN category data is returned to the customer site THEN it SHALL come from the
   public catalog API with the category included.

### Requirement 8 — Phase-1 submission (no online payment)

**User Story:** As a customer, I want to submit my booking as a request and get
clear payment instructions, so that I can pay the advance to confirm.

#### Acceptance Criteria

1. WHEN the customer submits on the Payment step THEN the system SHALL create a
   `pending` booking that holds the slot, using the existing public booking
   creation path and server-authoritative pricing.
2. WHEN the booking is created THEN the system SHALL return the advance payable,
   the payment instructions, and a reference token, and the UI SHALL display them
   and a link to track the booking.
3. WHEN the customer has not agreed to the Terms & Conditions THEN the system
   SHALL disable "Submit request".
4. WHEN submission fails due to a slot conflict THEN the system SHALL surface the
   409 "Slot not available" message and SHALL prompt the customer to pick another
   slot/date.
5. WHERE online payment is not yet integrated THEN the system SHALL NOT require
   payment to submit, AND the minimum advance shown SHALL be read from the plan
   (`advance_paise`); the design SHALL leave a clear seam so a later phase can make
   advance payment mandatory without reworking this flow.

### Requirement 9 — Mobile-first, accessible, small bundle

**User Story:** As a customer on a phone, I want the whole flow to fit my screen
and load fast, so that booking is effortless.

#### Acceptance Criteria

1. WHEN any booking screen is shown on a mobile viewport THEN content SHALL NOT
   overflow horizontally and all primary actions SHALL be reachable within thumb
   reach.
2. WHEN the booking page loads THEN the added JavaScript SHALL keep the booking
   page within the project's bundle target (under ~150 KB gzipped) and SHALL use
   runtime API calls for availability/pricing (no SSR).
3. WHEN interactive controls are rendered THEN they SHALL have accessible labels
   and visible focus states, and selected states SHALL be conveyed non-visually
   (e.g. `aria-pressed`).

## Test Cases (mandatory — touches money & pricing)

Per `tech.md`, this spec touches money and must list explicit test cases. These
are server-side unless noted.

### Kids / adults pricing (unit, property-friendly)
- K1: kid charge per kid = whole-rupee round-half-up of
  (kid_pct × extra_guest_paise / 100), i.e. the result is always a multiple of 100
  paise, for a range of rates and percentages (0, 50, 100). Example: adult extra
  = ₹150, kid_pct = 50 -> kid = ₹75 (7500 paise); adult extra = ₹149, kid_pct = 50
  -> ₹74.50 rounds to ₹75 (7500 paise, not 7450).
- K2: raising `extra_guest_paise` increases the computed kid charge proportionally
  (no frozen kid price).
- K3: guest-allowance rule — adults+kids within `people_allowed` incur no extra
  charge; beyond it, the documented split rule charges adults at
  `extra_guest_paise` and kids at the kid rate.
- K4: `kid_pct = 0` yields zero kid charge; `kid_pct = 100` charges kids at the
  full extra-guest rate.
- K5: total guest count > `max_people_allowed` is rejected (validation), no
  booking created.
- K6: all pricing outputs are integer paise; client-sent money/totals are ignored.

### Special-decor category
- C1: migration adds the category column + CHECK constraint; existing rows get the
  documented default; invalid category values are rejected by the DB.
- C2: admin create/edit validates category; an unknown category returns 422.
- C3: public catalog returns category; Addons rendering groups by category and
  omits empty categories (component test).

### Booking summary correctness
- S1: Balance = Total − Advance payable for a variety of drafts (component test
  against server preview values).
- S2: summary reflects server preview only; changing an add-on re-prices via the
  preview endpoint (component test with a faked API).

### Disallowed times (integration)
- T1: a branch disallowed range makes an overlapping open-mode start unavailable
  and rejects a customer booking for that window (422/validation), while an
  outside-range window remains bookable.
- T2: disallowed-range validation (start < end) rejects a bad admin config (422).
- T3: changing disallowed ranges does not alter existing bookings.

### Offers showcase (integration + component)
- O1: the public offers endpoint returns only safe fields (code, description,
  validity) for active, customer-visible coupons and excludes inactive ones.
- O2: the home showcase omits cleanly when there are no active offers (component).

### Guests in review (component)
- G1: the summary/review shows adults and kids counts and a kids charge line only
  when the kids extra-guest amount > 0.

### Submission (integration, real Postgres)
- B1: submitting a valid draft creates exactly one `pending` booking holding the
  slot; response includes advance, instructions, token.
- B2: concurrent submission of the same slot — exactly one wins, the other gets
  409 (reuses the existing concurrency test guarantees).
- B3: submission without agreeing to terms is blocked client-side; server still
  validates inputs independently.

## Notes / Decisions

- The guest-allowance split rule (which of adults/kids fill `people_allowed`
  first, and how kids beyond the allowance are charged) is a pricing decision to
  be finalized in Design; it MUST live as one documented rule in
  `services/pricing.py`. Proposed default for Design review: adults fill the
  allowance first; every guest beyond `people_allowed` is an extra, charged at the
  adult extra-guest rate for adults and the kid rate for kids. Kids under 3 are
  not counted or charged.
- Kids percentage is stored per-plan (new column, e.g. `kid_price_pct`,
  integer 0–100, documented default). It modifies only the kid extra-guest charge;
  it does not change plan base price.
- Kid charge rounds to a WHOLE RUPEE (multiple of 100 paise), half-up — never a
  fractional rupee. This is a deliberate rounding rule for kid pricing only;
  other money keeps its existing paise-level computation.
- The time-selection UX is unchanged from today: fixed-slot branches show
  predefined slots; open-mode branches pick duration then start window. This spec
  only re-skins/relocates that control into the new screen, not its logic.
- `advance_paise` already exists on `plans`; this spec only ensures the admin form
  exposes it and the summary reads it. Mandatory-advance enforcement is deferred to
  the PhonePe spec.
- No new runtime infrastructure. Changes are schema (two columns + migration),
  pricing logic, admin form fields, public catalog fields, and the Astro booking
  island(s).
