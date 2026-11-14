# Implementation Plan — Customer Booking Flow v2

Tasks are ordered so the schema and server-authoritative pricing land first
(with tests), then the API surface, then admin, then the customer site. Optional
sub-tasks are marked with `*`.

> Migration numbering: the live DB is at **0016**. All new revisions chain off
> 0016 as 0017–0022. Do NOT reuse 0015/0016.

- [ ] 1. Schema: kids %, decor category, kids on bookings, disallowed times,
  coupon offer fields, advance rules
  - [ ] 1.1 Add `plans.kid_price_pct` (SMALLINT, default 50, CHECK 0–100) to the
    `Plan` model + migration `0017_add_kid_price_pct_to_plans`
  - [ ] 1.2 Add `special_decor_items.category` (TEXT, default `extra_decoration`,
    CHECK in the three values) to the model + migration
    `0018_add_category_to_special_decor_items`; define
    `SPECIAL_DECOR_CATEGORIES` constant
  - [ ] 1.3 Add `bookings.kids` (SMALLINT, default 0, CHECK `kids >= 0`) to the
    `Booking` model + migration `0019_add_kids_to_bookings`
  - [ ] 1.4 Add `location_disallowed_times` table + model
    (`location_disallowed_time.py`) with FK (ON DELETE CASCADE), start/end,
    optional `max_duration_minutes`, note, is_active, CHECK `start < end` +
    migration `0020_create_location_disallowed_times`
  - [ ] 1.5 Add `coupons.name` (TEXT NULL), `coupons.description` (TEXT NULL),
    `coupons.is_public` (BOOLEAN NOT NULL default false) to the `Coupon` model +
    migration `0021_add_name_description_public_to_coupons`
  - [ ] 1.6 Add `advance_rules` table + model (`advance_rule.py`): FK to
    `locations` (ON DELETE CASCADE, indexed), `min_total_paise`, `advance_paise`,
    `is_active`, CHECKs (both `>= 0`), unique `(location_id, min_total_paise)`
    (`uq_advance_rules_location_threshold`) + migration `0022_create_advance_rules`
  - [ ] 1.7 Verify all six migrations apply cleanly on a seeded DB (upgrade +
    downgrade), additive with server defaults
  - _Requirements: 6.2, 7.1, 7.2, 10.1, 10.2, 11.2, 12.1, 12.2_

- [ ] 2. Pricing: kids charge + guest-allowance rule + advance resolution
  - [ ] 2.1 Add `_round_to_whole_rupee` and `kid_rate_paise(plan)` to `pricing.py`
    (whole-rupee, derived from current `extra_guest_paise`)
  - [ ] 2.2 Add `kids` to `ValidatedRequest`; replace `_extra_guest_paise(plan,
    people)` with the documented adults-first allowance rule charging adult extras
    at the plan rate and kid extras at `kid_rate_paise`
  - [ ] 2.3 Add `kid_extra_guest_paise` to `PriceBreakdown` (combined
    `extra_guest_paise` unchanged)
  - [ ] 2.4 Add pure `resolve_advance_paise(rules, final_total_paise, *,
    fallback_paise)` (highest matching threshold wins; no match → `fallback_paise`
    = the plan's `advance_paise`); add `advance_paise` to `PriceBreakdown`; call it
    in `compute_booking_price` after the final total is known, passing the plan's
    advance as the fallback (rules + fallback passed in, no DB in `pricing.py`)
  - [ ] 2.5 Unit tests K1–K4, K6 + `kids=0` regression; A1 advance resolution
    (highest wins, no-match → fallback, empty rules → fallback); all
    pure/property-friendly
  - _Requirements: 6.1, 6.3, 6.3a, 6.4, 6.7, 12.3, 12.4, 12.6_

- [ ] 3. Validation + booking service: kids, disallowed times, advance wiring
  - [ ] 3.1 Add `kids` param to `validate_booking_request`; cap check on
    `people + kids` vs `max_people_allowed`; adults ≥ 1; populate
    `ValidatedRequest.kids`
  - [ ] 3.2 Pure `is_time_disallowed(ranges, start, duration_minutes)` helper in
    `services/slots.py` + unit truth-table test
  - [ ] 3.3 Enforce disallowed ranges in `_enforce_booking_time` (customer always;
    admin unless override) and in open-mode availability generation
  - [ ] 3.4 Load the location's active `advance_rules` in the booking service and
    pass them into `compute_booking_price` for preview + create so `advance_paise`
    is in every breakdown
  - [ ] 3.5 Persist `bookings.kids` in `create_customer_booking` /
    `create_admin_booking`; thread `kids` through preview
  - [ ] 3.6 Integration tests K5 (cap), T1/T3 (disallowed), adults=0 → 422;
    A2 (advance identical in preview/create), A4 (advance vs final total w/ coupon)
  - _Requirements: 6.4, 6.5, 10.3, 10.4, 10.5, 12.5, 12.6, 12.8_

- [ ] 4. API schemas + public catalog + offers + advance-rule endpoints
  - [ ] 4.1 Add `kids` to `PreviewBase`, `BookingCreate`, `BookingUpdate`
    (default 0, ge=0); `kid_extra_guest_paise` and `advance_paise` to
    `PriceBreakdownRead`; `kids` to `BookingRead` / `BookingListItem`
  - [ ] 4.2 Add `kid_price_pct` to `PlanRead` and `category` to `SpecialDecorRead`;
    wire through `services/catalog.py`
  - [ ] 4.3 Add `name`/`description`/`is_public` to admin coupon create/update +
    `CouponRead`; add `PublicOfferRead` + `GET /api/v1/public/offers` +
    `coupon.list_public_offers(db, on=...)` returning active+public, in-validity
    coupons with safe fields only (code, name, description, validity)
  - [ ] 4.4 Add disallowed-times admin schemas + CRUD endpoints
    (`GET/POST/DELETE /admin/locations/{id}/disallowed-times`, admin-only)
  - [ ] 4.5 Add advance-rule schemas (`AdvanceRuleCreate`/`AdvanceRuleRead`) +
    CRUD endpoints (`GET/POST/DELETE /admin/locations/{id}/advance-rules`,
    admin-only) + a small `services/advance_rule.py` owning the transaction;
    duplicate threshold → 409
  - [ ] 4.6 Integration tests O1 (offers safe fields; private/inactive/out-of-
    validity excluded), T2 (bad range → 422), A3 (advance-rule CRUD: duplicate →
    409, cross-location ok, negative → 422, staff → 403)
  - _Requirements: 6.6, 7.6, 10.1, 10.2, 11.1, 11.2, 11.3, 11.4, 11.6, 12.1, 12.2, 12.9_

- [ ] 5. Admin UI — catalog forms, coupon fields, disallowed times, advance rules
  - [ ] 5.1 Special-decor create/edit: Category select (3 labels → enum value) +
    zod; show category in the decor list
  - [ ] 5.2 Plan create/edit: "Kids price %" (0–100, default 50) + ensure
    "Minimum advance (₹)" bound to `advance_paise`; zod mirrors API
  - [ ] 5.3 Disallowed-times manager UI under branch settings (list/add/remove)
  - [ ] 5.4 Coupon create/edit: Name, Description (plain text), and Public toggle;
    show public state in the coupon list; zod mirrors API
  - [ ] 5.5 Advance-rules manager UI under branch settings (list sorted by
    threshold, add/remove; helper text "highest matching threshold wins; no match →
    the plan's minimum advance"); surface duplicate-threshold 409 inline
  - [ ] 5.6* Vitest for the category select, kids-% validation, advance-rule form
  - _Requirements: 6.6, 7.3, 10.1, 11.2, 12.1, 12.2_

- [ ] 6. Customer site: home widget, offers, floating call
  - [ ] 6.1 `HomeBookingWidget` island: branch dropdown + date (default today, no
    past) + Book Now (→ `/book?location=slug&date=`) + Call now (selected branch's
    phone; prompt to pick a branch when none selected)
  - [ ] 6.2 `OffersShowcase` island on the hero (fetch `/public/offers`, render
    code + name + description + validity; omit entirely when empty)
  - [ ] 6.3 `FloatingCall` island in `Base.astro` (branch picker → `tel:` from the
    branch's phone; branches without a phone are not shown), styled like the
    WhatsApp button
  - [ ] 6.4 Vitest O2 (offers omit when empty / none public) + widget
    navigation/prompt
  - _Requirements: 1.1–1.6, 2.1–2.3, 11.1–11.6_

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
    Subtotal + Advance + Balance "payable at venue" expanded); Advance read from
    `breakdown.advance_paise`; guests (adults+kids) and kids line when > 0;
    server-preview only; isolate submit handler as the PhonePe seam
  - [ ] 7.6 Vitest S1 (Balance = Total − Advance from server), S2 (re-price on
    change), G1 (guests + kids line), wizard skip/required/terms
  - [ ] 7.7 Mobile overflow + a11y pass (labels, focus, aria-pressed)
  - _Requirements: 3.1–3.6, 4.1–4.9, 5.1–5.7, 8.1–8.5, 9.1–9.3, 12.5_

- [ ] 8. Wire-up, docs, full verification
  - [ ] 8.1 Regenerate admin/web TS types from the updated OpenAPI schema
  - [ ] 8.2 Update docs (`docs/`) with the kids rule, decor categories, disallowed
    times, coupon public offers, and the advance-rule resolution + plan-advance
    fallback. `.env.example` unchanged (no new config)
  - [ ] 8.3 Run `ruff`, `pytest`, `eslint`, `vitest`; fix to green
  - [ ] 8.4 Manual smoke on staging: home widget → branch screen → 5 steps →
    submit; kids pricing; decor categories; disallowed time blocked; public offers
    shown (and hidden when none public); advance reflects the matched rule and the
    plan-advance fallback when no rule matches
  - _Requirements: all; Definition of Done (structure.md)_
