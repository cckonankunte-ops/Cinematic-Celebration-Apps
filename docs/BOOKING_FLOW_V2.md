# Customer Booking Flow v2

This note documents the behaviours added by the `customer-booking-flow-v2`
spec. All of it is **server-authoritative** (the client sends only IDs,
quantities, and guest counts; the server computes every rupee) and
**DB-driven** (no new environment variables — `.env.example` is unchanged).

## 1. Kids pricing (`plans.kid_price_pct`)

Children aged 3–10 are charged a reduced extra-guest rate; kids under 3 are
neither counted nor charged (the UI doesn't collect them).

- Each plan has `kid_price_pct` (SMALLINT, 0–100, default **50**).
- The per-kid charge is derived at pricing time from the plan's **current**
  extra-guest rate, rounded half-up to a whole rupee:
  `kid_rate = round_to_whole_rupee(kid_price_pct% × plan.extra_guest_paise)`.
  Example (pct = 50): adult extra ₹150 → kid ₹75. Raising the adult rate later
  automatically raises the kid rate (no stored kid price).

### Guest-allowance rule (the single documented rule)

Total guests = `adults (people)` + `kids`. Adults fill the plan's included
allowance first; any remaining allowance covers kids:

```
allowed       = plan.people_allowed
adult_extras  = max(0, adults - allowed)
allowance_left= max(0, allowed - adults)
kid_extras    = max(0, kids - allowance_left)
extra_guest_paise = adult_extras * plan.extra_guest_paise
                  + kid_extras   * kid_rate_paise(plan)
```

When `kids == 0` this reduces exactly to the old adults-only behaviour, so all
prior pricing is unchanged. The booking cap check uses `adults + kids` against
`plan.max_people_allowed`; adults must be ≥ 1.

- Storage: `bookings.people` stays the **adult** count (backward compatible);
  `bookings.kids` (SMALLINT ≥ 0, default 0) is added alongside.
- Breakdown: `PriceBreakdownRead.extra_guest_paise` stays the combined figure;
  `kid_extra_guest_paise` is the kid-only portion so the summary can show a
  "Kids (n)" line.

## 2. Special-decor categories (`special_decor_items.category`)

Each decor item has a `category` (TEXT, default `extra_decoration`, CHECK in the
three values). Stored lowercase; the UI maps to labels:

| Stored value       | Label            |
|--------------------|------------------|
| `extra_decoration` | Extra Decoration |
| `gifts`            | Choose Gifts     |
| `special_service`  | Special Service  |
| `admin_only`       | Only Admin       |

`admin_only` items (migration 0023) are staff-only: the public decor list omits
them, customer create/preview reject their ids (422), and the admin booking form
loads decor from `GET /api/v1/admin/booking-options/special-decor`, which
includes them.

The customer Add-ons step groups decor under these headings in that fixed
order; empty categories are omitted. Admin creates/edits the category on each
decor item.

## 3. Disallowed booking times (`location_disallowed_times`)

Per-branch time ranges during which customers cannot start a booking.

- Columns: `start_time`, `end_time` (CHECK `start < end`), optional
  `max_duration_minutes` (when set, the range only blocks bookings of that
  duration or shorter), `note`, `is_active`. FK to `locations`
  (`ON DELETE CASCADE`).
- Enforcement is pure + shared: `is_time_disallowed(ranges, start, duration)`
  returns true when the booking's window overlaps an active range whose
  `max_duration_minutes` is NULL or ≥ the booking duration.
  - Open-mode availability marks disallowed starts `is_available = false`.
  - Booking create rejects a disallowed window for **customers**.
  - **Staff/admin may override** (admin create/edit passes
    `override_disallowed = true`); customers never bypass.
- Admin CRUD: `GET/POST/DELETE /api/v1/admin/locations/{id}/disallowed-times`
  (admin-only), managed under Catalog → Location settings.

## 4. Coupon public offers (`coupons.name/description/is_public`)

Coupons gain admin-written display fields for a home-page showcase:

- `name` (TEXT, nullable) — short label (e.g. "Weekday Special").
- `description` (TEXT, nullable) — plain-text blurb.
- `is_public` (BOOLEAN, default **false**) — only public coupons appear on the
  home page. Existing coupons default to private, so nothing leaks on deploy.

These fields are **display-only** and never affect the discount math (coupons
stay server-authoritative: the client sends only the code; the server validates
and computes the discount).

- Public endpoint: `GET /api/v1/public/offers` returns **safe fields only**
  (`code`, `name`, `description`, `effective_from`, `effective_to`) for active,
  public, in-validity coupons. It never exposes value, cap, usage limits, or
  percentage-base internals. Empty list ⇒ the home `OffersShowcase` renders
  nothing (no empty widget, no layout shift).

## 5. Advance resolution (`advance_rules`)

Advance payable is resolved from per-branch threshold rules against the
booking's **final total** (after admin discount AND coupon), not a flat value.

- Table `advance_rules`: `min_total_paise`, `advance_paise` (both ≥ 0),
  `is_active`, FK to `locations` (`ON DELETE CASCADE`), unique
  `(location_id, min_total_paise)` so thresholds are distinct per branch.
- Resolution (pure, unit-tested): the **highest** threshold the final total
  meets wins. When no active rule matches (or there are none), the advance
  **falls back to the plan's `advance_paise`**. Ties are impossible (unique
  threshold per branch).
- `PriceBreakdownRead.advance_paise` carries the resolved advance through
  **both preview and create**, so the customer summary's "Advance payable" and
  "Balance = Total − Advance payable" are server-authoritative on every step
  (the client computes no money).
- Admin CRUD: `GET/POST/DELETE /api/v1/admin/locations/{id}/advance-rules`
  (admin-only). Creating a duplicate threshold for a branch returns **409**;
  negative values are rejected **422**. The admin UI lists rules sorted by
  threshold with the helper line: "highest matching threshold wins; no match →
  the plan's minimum advance".

> **PhonePe seam:** when the gateway lands, it charges exactly this
> `advance_paise`. The resolution rule does not change — only the Payment step's
> submit handler swaps "Submit request" for "Pay ₹{advance} and book".

## 6. Customer site flow

- **Home** (`index.astro`): `HomeBookingWidget` (branch + date → `/book`, or
  Call now) and `OffersShowcase` in the hero; a site-wide `FloatingCall` button
  in `Base.astro` alongside the WhatsApp FAB.
- **/book** (`BookingWizard`): one island folds the branch screen + a 5-step
  flow — **Basic Details → Occasion → Cake → Add-ons → Payment**. An always-
  visible Overview lets the customer change branch/date in place. Occasion,
  Cake, and Add-ons are skippable ("Skip" / "Add later after booking"). The
  Payment step gates submit behind a Terms & Conditions checkbox. Guest counts
  flow as `people` (adults) + `kids`.
- **Summary** (`BookingSummary`): collapsible, driven entirely by the server
  preview. Collapsed shows Total + Advance payable; expanded shows line items,
  Subtotal, coupon, a Kids line when `kid_extra_guest_paise > 0`, Advance
  payable, and Balance ("payable at venue"). No client-side money math.

## Migrations

Six additive revisions chain off `0016` (all backfill via `server_default`):

| Revision | Change |
|----------|--------|
| `0017_add_kid_price_pct_to_plans`              | `plans.kid_price_pct` (default 50, CHECK 0–100) |
| `0018_add_category_to_special_decor_items`     | `special_decor_items.category` (default `extra_decoration`, CHECK) |
| `0019_add_kids_to_bookings`                    | `bookings.kids` (default 0, CHECK ≥ 0) |
| `0020_create_location_disallowed_times`        | disallowed-times table (+ FK, CHECK) |
| `0021_add_name_description_public_to_coupons`  | `coupons.name/description/is_public` (default false) |
| `0022_create_advance_rules`                    | advance-rules table (+ FK, CHECKs, unique threshold) |

## Verifying this feature

Run the standard gate (see `VERIFICATION.md`). Note for the frontends:

- The OpenAPI contract artifact (`apps/api/openapi.json`) must be regenerated so
  it reflects the new fields/endpoints: `python -m scripts.export_openapi`.
- The admin and web apps use hand-written TypeScript types (the generated
  `apps/admin/src/api/schema.ts` is an opt-in stub nothing imports), so no
  regenerated types are required for the build; `npm run gen:api` only refreshes
  that unused stub.

## Staging smoke checklist (manual)

Run against staging after deploying the branch. Confirm end-to-end:

1. **Home widget** — pick a branch + a future date, "Book Now" lands on
   `/book?location=<slug>&date=<iso>` with the date prefilled; "Call now" dials
   the branch (and prompts to pick a branch when none is selected).
2. **5-step flow** — Basic Details → Occasion → Cake → Add-ons → Payment. Skip
   Occasion/Cake/Add-ons and confirm you still reach Payment; the Submit button
   stays disabled until the Terms checkbox is ticked.
3. **Kids pricing** — set adults within the allowance and add kids beyond it;
   the summary shows a "Kids (n)" line and the total reflects the reduced kid
   rate (e.g. adult extra ₹150 → kid ₹75 at pct 50).
4. **Decor categories** — Add-ons groups decor under Extra Decoration / Choose
   Gifts / Special Service; an empty category is hidden.
5. **Disallowed time blocked** — configure a disallowed range for the branch;
   a customer cannot start a booking in it, but an admin booking can override.
6. **Public offers** — flip a coupon to public with a name/description; it
   appears on the home page. Make all coupons private; the showcase disappears.
7. **Advance reflects rules** — add advance rules for the branch; the summary's
   "Advance payable" matches the highest threshold the final total meets, and
   falls back to the plan's advance when no rule matches. "Balance" = Total −
   Advance.
8. **Submit** — the booking request is created `pending`, the success panel
   shows the advance + payment instructions + tracking token, and the status
   page resolves the token.
