# Implementation Plan — Customer Booking Flow v2

Tasks are ordered so the schema and server-authoritative pricing land first
(with tests), then the API surface, then admin, then the customer site. Optional
sub-tasks are marked with `*`.

- [ ] 1. Schema: add kids, kid pricing, decor category, disallowed times
  - [ ] 1.1 Add `plans.kid_price_pct` (SMALLINT, default 50, CHECK 0–100) to the
    `Plan` model + migration `0015_add_kid_price_pct_to_plans`
  - [ ] 1.2 Add `special_decor_items.category` (TEXT, default `extra_decoration`,
    CHECK in the three values) to the model + migration
    `0016_add_category_to_special_decor_items`; define
    `SPECIAL_DECOR_CATEGORIES` constant
  - [ ] 1.3 Add `bookings.kids` (SMALLINT, default 0, CHECK `kids >= 0`) to the
    `Booking` model + migration `0017_add_kids_to_bookings`
  - [ ] 1.4 Add `location_disallowed_times` table + model
    (`location_disallowed_time.py`) with FK (ON DELETE CASCADE), start/end,
    optional `max_duration_minutes`, note, is_active, CHECK `start < end` +
    migration `0018_create_location_disallowed_times`
  - [ ] 1.5 Verify migrations apply cleanly on a seeded DB (upgrade + downgrade)
  - _Requirements: 6.2, 7.1, 7.2, 10.1, 10.2_

- [ ] 2. Pricing: kids charge + guest-allowance rule
  - [ ] 2.1 Add `_round_to_whole_rupee` and `kid_rate_paise(plan)` to `pricing.py`
    (whole-rupee, derived from current `extra_guest_paise`)
  - [ ] 2.2 Add `kids` to `ValidatedRequest`; replace `_extra_guest_paise(plan,
    people)` with the documented adults-first allowance rule charging adult extras
    at the plan rate and kid extras at `kid_rate_paise`
  - [ ] 2.3 Add `kid_extra_guest_paise` to `PriceBreakdown` (combined
    `extra_guest_paise` unchanged)
  - [ ] 2.4 Unit tests K1–K4, K6 + `kids=0` regression (pure, property-friendly)
  - _Requirements: 6.1, 6.3, 6.3a, 6.4, 6.7_

- [ ] 3. Validation + booking service: kids + disallowed times
  - [ ] 3.1 Add `kids` param to `validate_booking_request`; cap check on
    `people + kids` vs `max_people_allowed`; adults ≥ 1; populate
    `ValidatedRequest.kids`
  - [ ] 3.2 Pure `is_time_disallowed(ranges, start, duration_minutes)` helper in
    `services/slots.py` + unit truth-table test
  - [ ] 3.3 Enforce disallowed ranges in `_enforce_booking_time` (customer always;
    admin unless override) and in open-mode availability generation
  - [ ] 3.4 Persist `bookings.kids` in `create_customer_booking` /
    `create_admin_booking`; thread `kids` through preview
  - [ ] 3.5 Integration tests K5 (cap), T1/T3 (disallowed), adults=0 → 422
  - _Requirements: 6.4, 6.5, 10.3, 10.4, 10.5_

- [ ] 4. API schemas + public catalog + offers endpoint
  - [ ] 4.1 Add `kids` to `PreviewBase`, `BookingCreate`, `BookingUpdate`
    (default 0, ge=0); `kid_extra_guest_paise` to `PriceBreakdownRead`; `kids` to
    `BookingRead` / `BookingListItem`
  - [ ] 4.2 Add `kid_price_pct` to `PlanRead` and `category` to `SpecialDecorRead`;
    wire through `services/catalog.py`
  - [ ] 4.3 Add `PublicOfferRead` + `GET /api/v1/public/offers` +
    `coupon.list_public_offers(db, on=...)` (safe fields only)
  - [ ] 4.4 Add disallowed-times admin schemas + CRUD endpoints
    (`GET/POST/DELETE /admin/locations/{id}/disallowed-times`, admin-only)
  - [ ] 4.5 Integration tests O1 (offers safe fields), T2 (bad range → 422)
  - _Requirements: 6.6, 7.6, 10.1, 10.2, 11.1, 11.2, 11.3, 11.4_

- [ ] 5. Admin catalog forms
  - [ ] 5.1 Special-decor create/edit: Category select (3 labels → enum value) +
    zod; show category in the decor list
  - [ ] 5.2 Plan create/edit: "Kids price %" (0–100, default 50) + ensure
    "Minimum advance (₹)" bound to `advance_paise`; zod mirrors API
  - [ ] 5.3 Disallowed-times manager UI under branch settings (list/add/remove)
  - [ ] 5.4* Vitest for the category select + kids-% validation
  - _Requirements: 6.6, 7.3, 10.1_

- [ ] 6. Customer site: home widget, offers, floating call
  - [ ] 6.1 `HomeBookingWidget` island: branch dropdown + date (default today, no
    past) + Book Now (→ `/book?location=slug&date=`) + Call now; prompt when no
    branch
  - [ ] 6.2 `OffersShowcase` island on the hero (fetch `/public/offers`, omit when
    empty)
  - [ ] 6.3 `FloatingCall` island in `Base.astro` (branch picker → `tel:`), styled
    like the WhatsApp button
  - [ ] 6.4 Vitest O2 (offers omit when empty) + widget navigation/prompt
  - _Requirements: 1.1–1.6, 2.1–2.3, 11.1–11.3_

- [ ] 7. Customer site: branch screen + 5-step wizard + summary
  - [ ] 7.1 Add `adults`/`kids` to `BookingDraft` (keep `people`=adults mapping on
    send); `GuestCounter` (adults ≥ 1, kids ≥ 0)
  - [ ] 7.2 `BranchBookingScreen`: top Overview + Update (branch AND date), plan
    list, reuse `SlotPicker`/`OpenSlotPicker` unchanged
  - [ ] 7.3 Rework `BookingWizard` to 5 steps (Basic Details → Occasion → Cake →
    Addons → Payment); Occasion/Cake/Addons skippable; "Add later after booking";
    terms checkbox gates submit
  - [ ] 7.4 `DecorByCategory` (grouped, vertical on mobile, omit empty categories)
  - [ ] 7.5 `BookingSummary` collapsible (Total/Advance collapsed; line items +
    Subtotal + Advance + Balance "payable at venue" expanded); guests (adults+kids)
    and kids line when > 0; server-preview only; isolate submit handler as the
    PhonePe seam
  - [ ] 7.6 Vitest S1 (Balance = Total − Advance), S2 (re-price on change), G1
    (guests + kids line), wizard skip/required/terms
  - [ ] 7.7 Mobile overflow + a11y pass (labels, focus, aria-pressed)
  - _Requirements: 3.1–3.6, 4.1–4.9, 5.1–5.7, 8.1–8.5, 9.1–9.3_

- [ ] 8. Wire-up, docs, full verification
  - [ ] 8.1 Regenerate admin/web TS types from the updated OpenAPI schema
  - [ ] 8.2 Update `.env.example` + docs only if a default call number config is
    added (`PUBLIC_DEFAULT_CALL_NUMBER`); otherwise derive from first active branch
  - [ ] 8.3 Run `ruff`, `pytest`, `eslint`, `vitest`; fix to green
  - [ ] 8.4 Manual smoke on staging: home widget → branch screen → 5 steps →
    submit; kids pricing; decor categories; disallowed time blocked; offers shown
  - _Requirements: all; Definition of Done (structure.md)_
