# Requirements Document

## Introduction

This feature adds an "Edit booking" capability to the Cinematic Celebration admin panel and introduces multi-quantity add-ons across the booking flow.

Today the admin booking list (`BookingListPage.tsx`) has no edit action, and `BookingFormPage.tsx` only handles creation. The backend already has an `update_booking` service and a `PATCH /api/v1/admin/bookings/{id}` endpoint, so the edit path largely exists server-side but must be extended for add-on quantities. The admin edit UI is net-new.

Separately, add-ons currently cannot carry a quantity. The `booking_items` table has no `quantity` column, pricing in `services/pricing.py` emits exactly one line per selected item, and the request schemas use de-duplicated ID lists (`special_decor_ids`, `combo_ids`). Representing "2× Party Poppers" is therefore impossible today. This spec adds quantity for special-decor and combo add-ons (cake remains single-select), which is a database (Alembic migration) + pricing-service + schema change, not just a UI change.

This spec also introduces three pricing capabilities that apply to both the admin booking flow and the customer web booking flow. First, **cake weight-based pricing**: a cake's stored price is the base price for 0.5 kg, the customer or admin selects a weight in positive multiples of 0.5 kg, and the server computes the cake line price as `base × (weight / 0.5)`. Second, **admin-managed combos**: a Combo is an admin-authored, location-scoped bundle with just a name, a combo price in paise, an optional cake baseline, and an optional LED baseline. A Combo is **not** a fixed list of component items — the combo price already encapsulates whatever the admin bundled, and only cake and LED have variable "baseline + overage" behavior. When a Combo is selected on a booking the server starts from the combo price and adds a floored cake-upgrade delta (when the Combo has a cake baseline) and a floored LED-upgrade delta (when the Combo has an LED baseline). An admin may create multiple Combos per location. Third, **LED letters**: a global rate of ₹40 per letter (stored as a documented `4000` paise/letter constant) applies to an LED name/text field persisted on the booking. The letter count is the number of alphabetic A–Z characters only (case-insensitive, ignoring spaces and punctuation). LED applies both standalone (no combo covers LED, charged as `letter_count × 4000` paise) and inside a Combo (priced through the Combo's LED delta, emitting no separate standalone LED line). All three capabilities keep money in integer paise and pricing server-authoritative, with the client sending only identifiers, quantities, the chosen cake weight, and the LED name text.

This spec also establishes **field parity between create and edit**: every field on the admin Edit_Form is also present on the admin create form, and the customer web create form gains the new fields that apply to customers (Cake_Weight, LED_Name, and combo selection as a distinct line). Combos are shown as a **transparent, distinct selectable line** in both the admin booking UIs (create and edit) and the customer web booking UI, with the combo name and its computed line price visible in the live summary.

Finally, this spec introduces a **coupon-code feature**. This intentionally reintroduces a coupon-code concept that an earlier steering decision had declined to replicate; the user has explicitly requested it. Coupons are admin-managed, location-scoped catalog entities (like plans, cakes, and combos). A coupon is either a `flat` paise discount or a `percentage` discount with an optional maximum cap, applied to a configurable base that is either the pre-coupon total or an admin-selected subset of components. Both customers and admins apply a coupon by entering the code; the server validates the coupon and computes the discount. The coupon discount stacks on top of (and is independent of) the existing admin manual discount. Accordingly, the money math now includes a coupon discount applied **after** the admin manual discount: `total = subtotal + food + other + cleaning − admin_manual_discount − coupon_discount`, with the total clamped at `0` so a coupon can never make the total negative.

This spec also **flips the contact-field requirements**: a phone number becomes **mandatory** on every booking (admin create, admin Edit_Form, and customer web create), and email becomes **optional**. Today the booking email column is required/non-null and phone is optional; this spec reverses that so phone is required and email is nullable. Because a phone is now the per-customer identity, phone numbers are **normalized** to a canonical Indian-mobile form (last 10 digits, Indian mobile starting 6–9) for matching, and the **coupon per-customer usage limit is keyed on the normalized phone** rather than on email.

This spec also surfaces **payment-ledger recording and voiding on the Edit_Form**. An admin or staff member may record one or more payments against a booking — each with a method, an amount in paise, and an optional note — directly from the Edit_Form (and from admin create when an advance is taken at creation), and the Edit_Form shows the full payment history alongside the derived Amount_Paid and Amount_Due. Because payments are an append-only ledger, a wrong payment is never hard-deleted or mutated: an **admin-only void** inserts a REVERSING ledger entry — a new negative-amount row that references the original payment — so the ledger stays a complete, transparent audit trail and `Amount_Paid = SUM(amount_paise)` naturally nets the voided payment to zero effect. Voiding requires a reason, is permitted at most once per payment, cannot be applied to a reversal row, and writes a `payment_voided` audit event.

All work preserves the system invariants from the steering docs: money is integer paise, pricing is server-authoritative in `services/pricing.py`, Amount_Paid and Amount_Due are derived from the payments ledger and never stored, the client sends only IDs, quantities, the chosen cake weight, the LED name text, and the coupon code (client-sent totals, client-computed line prices, and client-sent coupon amounts are ignored), double-booking is prevented per `(location, plan, slot, date)` by the DB partial unique index, staff are restricted to their location in the service layer, and every state change writes a booking audit event.

### Decisions (resolved during requirements)

- **D1 — Quantity scope:** Quantity applies to special-decor and combo add-ons. Cake stays single-select.
- **D2 — Add-on UI:** Each decor/combo add-on uses a checkbox plus a numeric quantity stepper (quantity `0` means not selected).
- **D3 — Editable statuses:** Editing is allowed for `pending` and `accepted` bookings; blocked for `rejected` and `expired`.
- **D4 — Access:** `admin` and `staff` may edit; staff are restricted to their assigned location(s), consistent with create.
- **D5 — Live preview:** A dedicated server preview endpoint computes the authoritative price breakdown without saving. The client never computes money.
- **D6 — Cake weight pricing:** A cake's stored `price_paise` is the base price for 0.5 kg. The selectable Cake_Weight is any positive multiple of 0.5 kg (0.5, 1.0, 1.5, 2.0, …) with no maximum. The cake line price is `base_price_paise × (weight_kg / 0.5)` (0.5 kg = ×1, 1.0 kg = ×2, 1.5 kg = ×3, …). This applies to both the admin booking flow and the customer web booking flow. The default weight is 0.5 kg. The chosen weight is persisted on the booking's cake Add_On_Line (stored in half-kg units) so edits and the ledger reflect it; cake quantity remains `1` per D1.
- **D7 — Admin-managed combos:** A Combo is an admin-authored, location-scoped bundle with a name, a combo price in paise, an **optional** cake baseline in paise (`Combo_Cake_Baseline`), and an **optional** LED baseline in paise (`Combo_LED_Baseline`). A Combo is **not** a fixed list of component items: there is no combo-components table and no fixed/default bundled items. The combo price already encapsulates whatever the admin bundled; only cake and LED have variable "baseline + overage" behavior. An absent/null cake baseline means the Combo does not include a cake; an absent/null LED baseline means the Combo does not include LED letters. An admin may create multiple Combos per location. Combo catalog management is admin-only, consistent with the existing catalog router's `require_role("admin")`. Combos are a distinct selectable line in the booking form, separate from special-decor add-ons. A valid Combo needs a name, a combo price `≥ 0`, and each present baseline `≥ 0`.
- **D8 — Combo line pricing and cake/LED interaction:** When a Combo is selected on a booking, the Combo_Line_Price is:
  ```
  combo_line_price = combo_price_paise
      + (combo has cake baseline ? max(0, chosen_cake_weighted_price − Combo_Cake_Baseline) : 0)
      + (combo has LED baseline  ? max(0, (LED_Letter_Count × 4000) − Combo_LED_Baseline)   : 0)
  ```
  where `chosen_cake_weighted_price` is the chosen cake's base price × (Cake_Weight ÷ 0.5 kg) — the weight multiplier is applied **before** subtracting the cake baseline (per D6). The `Cake_Upgrade_Delta` and `LED_Upgrade_Delta` are each floored at `0` (a cheaper or equal cake/LED adds nothing). Combo quantity is always `1` and is not selectable. Cake interaction: when the selected Combo includes a cake (has a cake baseline), the chosen cake is priced **only** through the Combo cake-delta rather than also charging a separate standalone weighted cake line; when no selected Combo covers cake, the chosen cake is charged as a normal weighted cake line per D6. LED interaction: when the selected Combo includes LED (has an LED baseline), LED is priced **only** through the Combo LED-delta and no separate standalone LED line is emitted; when no selected Combo covers LED, LED is charged as a standalone line of `LED_Letter_Count × 4000` paise per D9.
- **D9 — LED letters:** LED letters cost a global `LED_Unit_Price` of `4000` paise (₹40) per letter, stored as a single documented constant rather than hardcoded in multiple places. A booking carries an `LED_Name` text field (e.g. "ARUNA"). The `LED_Letter_Count` is the count of alphabetic A–Z characters only, case-insensitive, ignoring spaces and punctuation (e.g. "HAPPY BIRTHDAY" = 13). When the LED_Name is empty or absent, LED_Letter_Count is `0` and no LED charge applies. LED applies both standalone (no selected Combo covers LED → standalone line `LED_Letter_Count × 4000` paise) and inside a Combo (Combo has an LED baseline → priced through the Combo LED-delta, no standalone LED line). LED pricing is server-authoritative: the client sends only the LED name text, never a computed LED price. LED_Name is persisted on the booking and pre-filled on the Edit_Form; this applies to both the admin booking flow and the customer web booking flow.
- **D10 — Field parity (create == edit):** The admin create form and the admin Edit_Form expose an identical field set (cake + Cake_Weight, decor/combo selections with quantity, LED_Name, occasion, and the Money_Fields the admin may set). The customer web create form gains the new customer-appropriate fields — cake + Cake_Weight, decor/combo quantities, LED_Name, and combo selection — but does **not** expose the admin-only Money_Fields (food, other, cleaning, discount), consistent with the existing rule that customer discount is always `0` and customers do not set admin money fields.
- **D11 — Transparent combos in all booking UIs:** Combos appear as a distinct, transparent selectable line in the admin create form, the admin Edit_Form, and the customer web create form. The price breakdown / live summary shows each selected Combo as its own line with the combo name and its computed Combo_Line_Price (amount), in both the admin and customer summaries.
- **D12 — Coupon model:** Coupons are admin-managed (create/edit) and location-scoped (per branch, like plans, cakes, and combos). A Coupon has a code, a Coupon_Type (`flat` or `percentage`), a value, an optional cap (for `percentage`), a configurable percentage base, an optional validity window, an active flag, and a configurable set of usage limits. A `flat` coupon subtracts a fixed paise amount from the final total. A `percentage` coupon applies a percentage, capped by the optional Coupon_Cap (paise; nil = uncapped), to a Coupon_Percentage_Base that is either `total` (the pre-coupon total = `subtotal + food + other + cleaning − admin_manual_discount`) or `selected_components` (an admin-chosen subset of {plan price, extra-person/extra-guest charge, add-ons (decor), combos, cake, food}; the coupon stores which components are included). The coupon discount is **independent of and stacks on top of** the admin manual discount; both reduce the total, and the existing admin-discount clamping behavior is unchanged. The money math becomes `total = subtotal + food + other + cleaning − admin_manual_discount − coupon_discount`, where `coupon_discount` is the flat paise value for `flat` coupons and `min(cap_if_present, round(pct × configured_base_paise))` for `percentage` coupons; the total is clamped at `0` so a coupon can never make the total negative. Coupon pricing is server-authoritative: the client sends only the coupon code, and the server validates the coupon (location match, active, validity window, enabled limits) and computes the coupon_discount, ignoring any client-sent coupon amount. Both customers (web) and admins (admin panel) may apply a coupon by entering/selecting the code. The applied coupon code and its computed coupon_discount are persisted on the booking, returned in the booking detail, pre-filled on the Edit_Form, and shown as a distinct line (code + amount) in the Price_Breakdown / summary. Enabled limits may be any combination of: validity window (`effective_from`/`effective_to`), active flag, one-time use, per-customer usage limit, total usage count limit, and minimum order value; applying a coupon that violates any enabled limit is rejected. The **per-customer usage limit is keyed on the booking's Normalized_Phone** (per D14), so the same customer reaching the system under different phone-number formats counts as one customer.
- **D13 — Contact fields (phone mandatory, email optional):** A phone number is **mandatory** on every booking — on the admin create form, the admin Edit_Form, and the customer web create form — and email becomes **optional**. The Booking_API SHALL reject a booking create or edit whose phone is missing or blank with a `422` `VALIDATION_ERROR`, and SHALL accept a booking with no email. This flips the previous rule where email was required/non-null and phone optional. Schema impact: the booking email column becomes nullable and the phone becomes a required field. Because existing rows may have a null phone, the NOT-NULL enforcement is a **design concern, not a hard DB `NOT NULL` constraint mandated here**: the recommended approach is to validate phone as required at the API/schema layer and either keep the phone column nullable at the DB level or backfill existing rows before adding a DB constraint; the design document resolves the exact migration strategy.
- **D14 — Phone normalization (Indian mobile):** Phone numbers are normalized to a canonical Indian-mobile form for storage-matching and for the coupon per-customer limit. Normalization SHALL strip spaces and dashes; accept a leading `0`, a `+91` country code, or no country code (defaulting the country code to `+91`); and reduce the number to the canonical **last 10 digits**. A valid Indian mobile is exactly 10 digits beginning with `6`, `7`, `8`, or `9`; a number that does not normalize to such a value is malformed and SHALL be rejected with a `422` `VALIDATION_ERROR`. Consequently `"+91 98765 43210"`, `"098765 43210"`, and `"9876543210"` all normalize to the same Normalized_Phone (`9876543210`) and key to the same customer. The Normalized_Phone is the value the coupon per-customer usage limit counts against (per D12/R21).
- **D15 — Record payments from the Edit_Form:** An admin or staff member may record one or more payments against a booking from the admin Edit_Form (and from admin create when an advance is taken at creation), each payment carrying a method (`cash`, `upi`, `card`, or `other`), an amount in paise, and an optional note. Multiple partial payments across time are supported (e.g. a ₹500 advance by UPI now, then later ₹2000 card plus ₹1500 cash). Each recorded payment appends one row to the existing `payments` ledger and writes the existing `payment_recorded` audit event. Recording is permitted for both `admin` and `staff`, with staff restricted to their assigned location(s), consistent with the existing `POST /api/v1/admin/bookings/{id}/payments` endpoint. The Edit_Form displays the full payment history (each ledger entry's amount, method, received timestamp, and who recorded it) oldest-first, plus the derived Amount_Paid and Amount_Due. Amount_Paid and Amount_Due remain DERIVED from the ledger (`Amount_Paid = SUM(amount_paise)`, `Amount_Due = total − Amount_Paid`, which may be negative when overpaid) and are never stored.
- **D16 — Void a payment via a reversing entry (admin-only):** Voiding a wrong payment never hard-deletes or mutates the original row. Instead it inserts a Reversing_Entry: a new `payments` row with a NEGATIVE amount equal to the negation of the original payment's amount, referencing the original payment through a new nullable `reverses_payment_id` self-FK (`payments.id`). Because `Amount_Paid = SUM(amount_paise)`, the reversing entry nets the voided payment to zero effect while preserving the full audit trail. Voiding is ADMIN-ONLY: staff may record payments but may not void; a non-admin void request returns `403`. A payment MAY be voided at most once, and a Reversing_Entry itself CANNOT be voided; a second void of the same payment or a void of a reversal row returns `422` (`PAYMENT_ALREADY_VOIDED` for a payment already voided, `PAYMENT_NOT_VOIDABLE` for a reversal row) and persists nothing. A reason/note is REQUIRED when voiding; a blank reason returns `422` `VALIDATION_ERROR`. Voiding writes a new `payment_voided` audit event recording the original payment id, the reversing entry, the acting admin, and the reason. The Edit_Form shows voided payments and their reversing entries in the history so the ledger stays transparent. Schema impact (resolved as a migration concern in the design): the existing `payments` `CHECK (amount_paise > 0)` is RELAXED to `CHECK (amount_paise <> 0)` so a negative reversing amount is allowed; a nullable `reverses_payment_id` FK (self-reference to `payments.id`) is added; and the `booking_events` type check-constraint list must include `payment_voided`. All of these go through reversible Alembic migrations.

## Glossary

- **Admin_Panel**: The React admin application under `apps/admin`.
- **Booking_API**: The FastAPI backend under `apps/api`.
- **Pricing_Service**: The server-authoritative pricing module `apps/api/app/services/pricing.py`.
- **Booking_Service**: The booking transaction/business-logic module `apps/api/app/services/booking.py`.
- **Edit_Form**: The Admin_Panel booking edit form pre-filled with an existing booking's values.
- **Preview_Endpoint**: A new admin endpoint that computes a price breakdown for a prospective edit without persisting any change.
- **Add_On**: A chargeable extra on a booking; of kind `cake`, `decor` (special-decor item), or `combo`.
- **Add_On_Line**: One persisted `booking_items` row: a kind, optional `item_id`, name snapshot, unit price snapshot, and quantity.
- **Quantity**: The integer count for a single decor or combo Add_On, where quantity multiplies the line's unit price. Cake quantity is always `1`.
- **Cake_Weight**: The customer- or admin-selected cake weight, expressed as a positive multiple of 0.5 kg (no maximum), persisted on the cake Add_On_Line in half-kg units. The default is 0.5 kg.
- **LED_Name**: The customer- or admin-entered LED name/text (e.g. "ARUNA") persisted on the booking, used to compute LED letter charges. May be empty or absent.
- **LED_Letter_Count**: The count of alphabetic A–Z characters in the LED_Name, case-insensitive, ignoring spaces and punctuation. `0` when LED_Name is empty or absent.
- **LED_Unit_Price**: The global LED rate of `4000` paise (₹40) per letter, stored as a single documented constant.
- **Combo**: An admin-authored, location-scoped bundle defined by a name, a combo price in paise, an optional cake baseline, and an optional LED baseline. A Combo is not a fixed list of component items; the combo price encapsulates whatever the admin bundled. Distinct from special-decor add-ons.
- **Combo_Cake_Baseline**: The optional paise baseline for the cake value included in a Combo, set by the admin when authoring the Combo, used as the subtraction baseline for the Cake_Upgrade_Delta. Absent/null means the Combo does not include a cake.
- **Combo_LED_Baseline**: The optional paise baseline for the LED value included in a Combo, set by the admin when authoring the Combo, used as the subtraction baseline for the LED_Upgrade_Delta. Absent/null means the Combo does not include LED letters.
- **Cake_Upgrade_Delta**: The floored difference `max(0, chosen_cake_weighted_price − Combo_Cake_Baseline)` added to a selected Combo's price when the Combo has a cake baseline, where `chosen_cake_weighted_price` applies the Cake_Weight multiplier before subtraction.
- **LED_Upgrade_Delta**: The floored difference `max(0, (LED_Letter_Count × LED_Unit_Price) − Combo_LED_Baseline)` added to a selected Combo's price when the Combo has an LED baseline.
- **Combo_Line_Price**: The server-computed price of a selected Combo Add_On_Line: `combo_price_paise + Cake_Upgrade_Delta (if cake baseline present) + LED_Upgrade_Delta (if LED baseline present)`.
- **Money_Field**: One of the admin-controlled charge inputs: `food_paise`, `other_paise`, `cleaning_paise`, `discount_paise` (the Admin_Manual_Discount).
- **Admin_Manual_Discount**: The admin-controlled manual discount `discount_paise`, clamped to `[0, plan.max_discount_paise]` and `0` when the plan does not allow a discount. It is distinct from and applied before the Coupon_Discount.
- **Coupon**: An admin-authored, location-scoped catalog entity defined by a code, a Coupon_Type, a value, an optional Coupon_Cap, a Coupon_Percentage_Base configuration, an optional validity window, an active flag, and an enabled set of Coupon_Limits. Managed like plans, cakes, and combos.
- **Coupon_Type**: The discount kind of a Coupon: `flat` (a fixed paise amount subtracted from the final total) or `percentage` (a percentage applied to the Coupon_Percentage_Base, capped by the optional Coupon_Cap).
- **Coupon_Percentage_Base**: For a `percentage` Coupon, the base the percentage applies to: `total` (the pre-coupon total = `subtotal + food + other + cleaning − Admin_Manual_Discount`) or `selected_components` (an admin-chosen subset of {plan price, extra-person/extra-guest charge, add-ons (decor), combos, cake, food}; the Coupon stores which components are included).
- **Coupon_Cap**: The optional maximum paise amount a `percentage` Coupon may discount. Nil means uncapped.
- **Coupon_Limit**: One of the configurable usage limits a Coupon may enable, each with its threshold: validity window (`effective_from`/`effective_to`), active flag, one-time use, per-customer usage limit, total usage count limit, and minimum order value. The Coupon stores which limits are enabled and their thresholds. The per-customer usage limit is counted per Normalized_Phone, not per email.
- **Normalized_Phone**: The canonical form of a booking's phone number used for per-customer matching and the coupon per-customer usage limit. Produced by stripping spaces and dashes, accepting a leading `0`, a `+91` country code, or no country code (country code defaults to `+91`), and reducing to the last 10 digits. A valid Normalized_Phone is exactly 10 digits beginning with `6`, `7`, `8`, or `9`. For example, `"+91 98765 43210"`, `"098765 43210"`, and `"9876543210"` all normalize to `9876543210`.
- **Coupon_Discount**: The server-computed paise amount a Coupon reduces from the total, applied after the Admin_Manual_Discount: the flat value for a `flat` Coupon, or `min(Coupon_Cap, round(pct × configured_base_paise))` for a `percentage` Coupon. The total is clamped at `0` so Coupon_Discount can never make the total negative.
- **Price_Breakdown**: The server-computed set of amounts: plan price, extra-guest charge, per-line add-on amounts, subtotal, Admin_Manual_Discount, food, other, cleaning, Coupon_Discount, total.
- **Amount_Paid**: The derived sum of recorded payments for a booking (from the payments ledger).
- **Amount_Due**: The derived value `total_paise − Amount_Paid` (may be negative when overpaid).
- **Payment_Entry**: One row in the append-only `payments` ledger for a booking, carrying a method (`cash`, `upi`, `card`, or `other`), an amount in paise, a received timestamp, the recording user, and an optional note. A Payment_Entry is never mutated or deleted after it is written.
- **Reversing_Entry**: A Payment_Entry inserted to void a prior Payment_Entry, carrying a NEGATIVE amount equal to the negation of the original payment's amount and a `reverses_payment_id` referencing the voided Payment_Entry. Because `Amount_Paid = SUM(amount_paise)`, a Reversing_Entry nets the voided payment to zero effect. A Reversing_Entry cannot itself be voided.
- **Voided_Payment**: A Payment_Entry that has been voided by an admin and therefore has an associated Reversing_Entry referencing it. The original row remains unchanged in the ledger; the Edit_Form shows it marked voided alongside its Reversing_Entry.
- **Slot_Conflict**: A violation of the partial unique index `uq_bookings_active_slot` on `(location_id, plan_id, slot_id, booking_date)` for `status IN ('pending','accepted')`.
- **Staff_User**: An authenticated user with role `staff`, restricted to assigned location(s).
- **Admin_User**: An authenticated user with role `admin`, who may act across all locations.

## Requirements

### Requirement 1: Edit action on the bookings list

**User Story:** As an admin or staff member, I want an Edit action on each booking row, so that I can open an editable form for that booking.

#### Acceptance Criteria

1. WHERE a booking has status `pending` or `accepted`, THE Admin_Panel SHALL display an Edit action on that booking's row and card.
2. WHERE a booking has status `rejected` or `expired`, THE Admin_Panel SHALL NOT display an Edit action for that booking.
3. WHEN the user activates the Edit action for a booking, THE Admin_Panel SHALL navigate to the Edit_Form for that booking's identifier.
4. THE Admin_Panel SHALL present the Edit action on both the mobile card layout and the `md+` table layout of the bookings list.

### Requirement 2: Load an existing booking into the Edit form

**User Story:** As an admin or staff member, I want the edit form pre-filled with the booking's current values, so that I can change only what I need.

#### Acceptance Criteria

1. WHEN the Edit_Form opens for a booking identifier, THE Booking_API SHALL return the booking's current field values, add-on lines with quantities, and derived Amount_Paid and Amount_Due.
2. WHEN the booking detail is returned, THE Edit_Form SHALL pre-fill booking name, occasion, booking date, cake, plan, name-on-cake, number of guests, slot, special-person name, phone, email, and message with the booking's current values, pre-filling email as empty when the booking has no email.
3. WHEN the booking detail is returned, THE Edit_Form SHALL pre-fill the Money_Fields (food, other, cleaning, discount) with the booking's current values in paise.
4. WHEN the booking detail is returned, THE Edit_Form SHALL pre-select each decor and combo Add_On with its current Quantity, and pre-select the current cake.
5. IF the requested booking identifier does not exist, THEN THE Booking_API SHALL return a `404` error with code `NOT_FOUND`.
6. IF a Staff_User requests a booking outside the Staff_User's assigned location(s), THEN THE Booking_API SHALL return a `403` error.

### Requirement 3: Edit every booking field

**User Story:** As an admin or staff member, I want every field on the edit form to be changeable, so that I can correct any part of a booking.

#### Acceptance Criteria

1. THE Edit_Form SHALL allow editing of booking name, occasion, booking date, cake, Cake_Weight, plan, name-on-cake, number of guests, slot, special-person name, phone, email, and message, requiring a phone number and treating email as optional.
2. THE Edit_Form SHALL allow editing of the Money_Fields: food, other, cleaning, and discount.
3. THE Edit_Form SHALL allow editing of decor and combo Add_On selections and their Quantities.
4. WHEN the user selects a plan, THE Edit_Form SHALL load that plan's slots and clear any slot that is not valid for the newly selected plan.
5. WHEN the user submits the Edit_Form, THE Admin_Panel SHALL send only identifiers, quantities, Cake_Weight, customer details, and Money_Fields to the Booking_API, and SHALL NOT send any computed total, cake price, or Combo_Line_Price.

### Requirement 4: Add-on quantity data model

**User Story:** As an admin, I want add-ons to carry a quantity, so that the same decor or combo can appear multiple times on a booking.

#### Acceptance Criteria

1. THE Booking_API SHALL store a `quantity` for each Add_On_Line in the `booking_items` table.
2. THE Booking_API SHALL enforce that `quantity` is an integer greater than or equal to `1` for every persisted Add_On_Line.
3. WHERE an Add_On_Line is of kind `cake`, THE Booking_API SHALL store its `quantity` as `1`.
4. THE Booking_API SHALL apply the `quantity` column through an Alembic migration that sets `quantity` to `1` for existing rows.
5. WHEN a booking's add-on lines are read, THE Booking_API SHALL return each line's kind, item identifier, name snapshot, unit price in paise, and `quantity`.

### Requirement 5: Server-authoritative pricing with quantity

**User Story:** As an admin, I want totals computed on the server with quantity multiplied in, so that pricing is correct and cannot be tampered with by the client.

#### Acceptance Criteria

1. THE Pricing_Service SHALL compute each decor and combo Add_On amount as its unit price in paise multiplied by its Quantity.
2. THE Pricing_Service SHALL compute the subtotal as plan price plus extra-guest charge plus the sum of all Add_On amounts.
3. THE Pricing_Service SHALL compute the total as subtotal plus food plus other plus cleaning minus discount.
4. THE Pricing_Service SHALL clamp an admin discount to the range `0` through the plan's maximum discount, and SHALL use `0` when the plan does not allow a discount.
5. WHEN the Booking_API receives any client-sent total, THE Booking_API SHALL ignore it and use the Pricing_Service result.
6. IF a submitted Quantity is less than `1` or is not an integer, THEN THE Booking_API SHALL return a `422` error with code `VALIDATION_ERROR`.

### Requirement 6: Live price preview during editing

**User Story:** As an admin or staff member, I want a live summary panel showing the current price breakdown while I edit, so that I can see the effect of my changes before saving.

#### Acceptance Criteria

1. THE Preview_Endpoint SHALL compute a Price_Breakdown from submitted identifiers, quantities, and Money_Fields without persisting any change to the booking.
2. WHEN the user changes a priced input (plan, people, cake, decor, combo, quantity, or a Money_Field) in the Edit_Form, THE Admin_Panel SHALL request an updated Price_Breakdown from the Preview_Endpoint.
3. WHEN a Price_Breakdown is returned, THE Admin_Panel SHALL display the plan line with people count, the extra-member charge, each Add_On line with its name and amount, the subtotal, food, other, cleaning, discount, total, Amount_Paid, and Amount_Due.
4. THE Admin_Panel SHALL display all amounts converted to rupees and SHALL send all amounts to the Booking_API in paise.
5. IF the Preview_Endpoint receives an invalid identifier or quantity, THEN THE Preview_Endpoint SHALL return a `422` error describing the invalid input.
6. IF a Staff_User requests a preview for a location outside the Staff_User's assigned location(s), THEN THE Preview_Endpoint SHALL return a `403` error.

### Requirement 7: Persist an edited booking

**User Story:** As an admin or staff member, I want to save my edits, so that the booking reflects the updated details and recomputed totals.

#### Acceptance Criteria

1. WHEN the user submits a valid edit, THE Booking_Service SHALL re-validate every submitted identifier against the booking's location and date and SHALL recompute the Price_Breakdown.
2. WHEN an edit changes the add-on selection, THE Booking_Service SHALL replace the booking's Add_On_Lines with the submitted lines and their Quantities within a single transaction.
3. WHEN an edit is persisted, THE Booking_Service SHALL update the booking's stored money columns to the recomputed Price_Breakdown values.
4. WHEN an edit is persisted, THE Booking_Service SHALL write an `edited` booking audit event recording the old and new money snapshot and the acting user.
5. IF validation of any submitted identifier fails, THEN THE Booking_API SHALL return a `422` error with code `ITEM_INVALID` and SHALL NOT persist any change.
6. WHILE an edit targets a booking with status `rejected` or `expired`, THE Booking_API SHALL reject the edit with a `422` error and SHALL NOT persist any change.

### Requirement 8: Slot-conflict handling on edit

**User Story:** As an admin or staff member, I want the system to prevent double-booking when I change plan, slot, or date, so that two active bookings never share the same slot.

#### Acceptance Criteria

1. WHEN an edit changes plan, slot, or booking date, THE Booking_Service SHALL apply the double-booking uniqueness rule on `(location, plan, slot, date)` for active bookings.
2. IF persisting an edit would create a Slot_Conflict, THEN THE Booking_API SHALL return a `409` error with message "Slot not available" and SHALL NOT persist any change.
3. WHEN an edit keeps the same plan, slot, and date as the booking's current values, THE Booking_Service SHALL NOT treat the booking's own existing slot allocation as a conflict with itself.

### Requirement 9: Access control for editing

**User Story:** As the system owner, I want edit access restricted by role and location, so that staff can only edit bookings for their own location.

#### Acceptance Criteria

1. THE Booking_API SHALL require a valid authenticated token with role `admin` or `staff` for the Edit_Form detail, Preview_Endpoint, and edit-submit requests.
2. IF a request has no valid token, THEN THE Booking_API SHALL return a `401` error.
3. IF an authenticated user's role is neither `admin` nor `staff`, THEN THE Booking_API SHALL return a `403` error.
4. WHILE a Staff_User edits, THE Booking_Service SHALL restrict the Staff_User to bookings within the Staff_User's assigned location(s) and SHALL return a `403` error for any other location.
5. WHERE the acting user is an Admin_User, THE Booking_Service SHALL permit editing bookings across all locations.

### Requirement 10: Generated types and schema contract

**User Story:** As a frontend developer, I want the admin types generated from the API schema, so that the edit UI stays in sync with the backend contract.

#### Acceptance Criteria

1. THE Booking_API SHALL expose the Add_On `quantity` field and the Preview_Endpoint in the OpenAPI schema.
2. THE Admin_Panel SHALL derive its booking and add-on TypeScript types from the generated API schema rather than hand-written duplicates.
3. THE Admin_Panel SHALL mirror the Booking_API validation rules (quantity minimum `1`, non-negative Money_Fields) in its zod form schema.

### Requirement 11: Cake weight selection

**User Story:** As a customer or admin, I want to select a cake weight in half-kilogram steps, so that I can order a larger cake and be charged proportionally.

#### Acceptance Criteria

1. THE Admin_Panel SHALL present a Cake_Weight selector in the booking create and Edit_Form, defaulting to 0.5 kg.
2. THE customer web booking flow SHALL present a Cake_Weight selector, defaulting to 0.5 kg.
3. WHEN the booking detail is returned, THE Edit_Form SHALL pre-fill the cake's current Cake_Weight.
4. WHEN the user submits a booking or edit, THE Admin_Panel and the customer web booking flow SHALL send the chosen cake identifier and Cake_Weight, and SHALL NOT send any computed cake price.
5. THE Admin_Panel SHALL offer Cake_Weight values as positive multiples of 0.5 kg with no maximum.

### Requirement 12: Cake weight pricing and persistence

**User Story:** As the system owner, I want cake pricing computed from weight on the server, so that larger cakes are priced correctly and cannot be tampered with by the client.

#### Acceptance Criteria

1. THE Pricing_Service SHALL compute the cake line price as the cake's base price in paise multiplied by `(Cake_Weight ÷ 0.5 kg)`.
2. THE Booking_API SHALL store the chosen Cake_Weight on the cake Add_On_Line in half-kilogram units in the `booking_items` table.
3. WHEN a booking's cake Add_On_Line is read, THE Booking_API SHALL return the cake's chosen Cake_Weight.
4. THE Booking_API SHALL apply the Cake_Weight column through an Alembic migration that sets the Cake_Weight to 0.5 kg for existing rows.
5. IF a submitted Cake_Weight is not a positive multiple of 0.5 kg, THEN THE Booking_API SHALL return a `422` error with code `VALIDATION_ERROR` and SHALL NOT persist any change.
6. WHERE the acting context is the customer web booking flow, THE Pricing_Service SHALL apply the same Cake_Weight pricing rule as the admin flow.

### Requirement 13: Admin combo management

**User Story:** As an admin, I want to create and edit combos as location-scoped bundles, so that I can offer multiple add-ons together at a combined price.

#### Acceptance Criteria

1. WHEN an admin creates a Combo, THE Booking_API SHALL store the Combo's name, combo price in paise, optional Combo_Cake_Baseline in paise, optional Combo_LED_Baseline in paise, and location identifier.
2. WHEN an admin edits a Combo, THE Booking_API SHALL update the Combo's name, combo price, Combo_Cake_Baseline, and Combo_LED_Baseline.
3. THE Booking_API SHALL allow an admin to create multiple Combos per location.
4. THE Booking_API SHALL require role `admin` for creating and editing a Combo.
5. IF a non-admin user requests to create or edit a Combo, THEN THE Booking_API SHALL return a `403` error.
6. IF a submitted Combo has a combo price below `0`, a present Combo_Cake_Baseline below `0`, or a present Combo_LED_Baseline below `0`, THEN THE Booking_API SHALL return a `422` error with code `VALIDATION_ERROR` and SHALL NOT persist any change.
7. WHERE a Combo's Combo_Cake_Baseline is absent, THE Booking_API SHALL treat the Combo as not including a cake, and WHERE a Combo's Combo_LED_Baseline is absent, THE Booking_API SHALL treat the Combo as not including LED letters.
8. THE Booking_API SHALL add the Combo_Cake_Baseline and Combo_LED_Baseline columns to the combos table through an Alembic migration.

### Requirement 14: Combo selection and delta pricing on a booking

**User Story:** As a customer or admin, I want selecting a combo to add its combined price plus any cake upgrade, so that the booking reflects the bundle and the chosen cake accurately.

#### Acceptance Criteria

1. THE Admin_Panel SHALL present Combos as a distinct selectable booking line, separate from special-decor add-ons, in the booking create and Edit_Form.
2. THE customer web booking flow SHALL present Combos as a distinct selectable booking line, separate from special-decor add-ons.
3. WHEN a Combo is selected on a booking, THE Pricing_Service SHALL compute the Combo_Line_Price as `combo_price_paise`, plus `max(0, chosen_cake_weighted_price − Combo_Cake_Baseline)` when the Combo has a Combo_Cake_Baseline, plus `max(0, (LED_Letter_Count × 4000) − Combo_LED_Baseline)` when the Combo has a Combo_LED_Baseline, where `chosen_cake_weighted_price` is the chosen cake's base price in paise multiplied by `(Cake_Weight ÷ 0.5 kg)`.
4. THE Pricing_Service SHALL floor the Cake_Upgrade_Delta at `0` when the chosen cake's weighted price is less than or equal to the Combo_Cake_Baseline, and SHALL floor the LED_Upgrade_Delta at `0` when `LED_Letter_Count × 4000` is less than or equal to the Combo_LED_Baseline.
5. THE Pricing_Service SHALL treat every selected Combo Add_On_Line as quantity `1`.
6. WHERE a selected Combo has a Combo_Cake_Baseline, THE Pricing_Service SHALL price the chosen cake through the Combo cake-delta and SHALL NOT also emit a separate standalone weighted cake line for that cake.
7. WHERE no selected Combo has a Combo_Cake_Baseline, THE Pricing_Service SHALL price the chosen cake as a standalone weighted cake line per Requirement 12.
8. WHERE a selected Combo has a Combo_LED_Baseline, THE Pricing_Service SHALL price LED through the Combo LED-delta and SHALL NOT also emit a separate standalone LED line.
9. WHERE no selected Combo has a Combo_LED_Baseline, THE Pricing_Service SHALL price LED as a standalone line of `LED_Letter_Count × 4000` paise per Requirement 16.
10. WHEN the user submits a booking or edit, THE Admin_Panel and the customer web booking flow SHALL send only the Combo identifier together with the chosen cake identifier, Cake_Weight, and LED_Name text, and SHALL NOT send any computed Combo_Line_Price, Cake_Upgrade_Delta, or LED_Upgrade_Delta.
11. WHEN the booking detail is returned, THE Edit_Form SHALL pre-fill the booking's current Combo selections.

### Requirement 15: Combo delta worked example

**User Story:** As a reviewer, I want concrete combo pricing examples in the spec, so that the delta rules are unambiguous for design and testing.

Item reference: fog entry `50000` paise (₹500), floor balloons `30000` paise (₹300), LED `4000` paise/letter (₹40). All amounts below are expressed in paise.

#### Acceptance Criteria

1. THE Pricing_Service SHALL, for Combo1 (combo price `70000` paise, Combo_LED_Baseline `20000` paise, no Combo_Cake_Baseline) with an LED_Name "ARUNA" (5 letters), compute a Combo_Line_Price of `70000` paise (`70000 + max(0, 5 × 4000 − 20000)` = `70000 + max(0, 20000 − 20000)`).
2. THE Pricing_Service SHALL, for Combo1 with an LED_Name "SANJAY" (6 letters), compute a Combo_Line_Price of `74000` paise (`70000 + max(0, 6 × 4000 − 20000)` = `70000 + max(0, 24000 − 20000)`).
3. THE Pricing_Service SHALL, for Combo2 (combo price `90000` paise, Combo_LED_Baseline `20000` paise, no Combo_Cake_Baseline), compute a Combo_Line_Price of `90000` paise when the LED delta is `0` (LED_Name of 5 letters or fewer).
4. THE Pricing_Service SHALL, for Combo3 (combo price `110000` paise, Combo_Cake_Baseline `40000` paise, Combo_LED_Baseline `20000` paise) with a chosen cake of base price `50000` paise at 0.5 kg and an LED_Name "ARUNA" (5 letters), compute a Combo_Line_Price of `120000` paise (`110000 + max(0, 50000 − 40000) + max(0, 20000 − 20000)`).
5. THE Pricing_Service SHALL, for Combo3 with the same chosen cake at 1.0 kg (chosen_cake_weighted_price `100000` paise) and an LED_Name "ARUNA" (5 letters), compute a Combo_Line_Price of `170000` paise (`110000 + max(0, 100000 − 40000) + max(0, 20000 − 20000)`).

### Requirement 16: LED letters name field and standalone pricing

**User Story:** As a customer or admin, I want to enter an LED name/text on a booking and be charged per letter, so that the booking reflects the LED letters ordered.

#### Acceptance Criteria

1. THE Admin_Panel SHALL present an LED_Name text input in the booking create and Edit_Form, and the customer web booking flow SHALL present an LED_Name text input.
2. THE Booking_API SHALL persist the LED_Name on the booking, and WHEN the booking detail is returned, THE Edit_Form SHALL pre-fill the booking's current LED_Name.
3. THE Pricing_Service SHALL compute the LED_Letter_Count as the number of alphabetic A–Z characters in the LED_Name, case-insensitive, ignoring spaces and punctuation.
4. WHERE no selected Combo has a Combo_LED_Baseline, THE Pricing_Service SHALL compute a standalone LED line price of `LED_Letter_Count × 4000` paise.
5. IF the LED_Name is empty or absent, THEN THE Pricing_Service SHALL compute an LED_Letter_Count of `0` and SHALL apply no LED charge.
6. WHEN the user submits a booking or edit, THE Admin_Panel and the customer web booking flow SHALL send only the LED_Name text, and SHALL NOT send any computed LED line price or LED_Letter_Count.
7. THE Booking_API SHALL add the LED_Name column to the bookings table through an Alembic migration.
8. WHERE the acting context is the customer web booking flow, THE Pricing_Service SHALL apply the same LED pricing rule as the admin flow.

### Requirement 17: Create/edit field parity

**User Story:** As an admin, I want the create booking form to have every field the edit form has, so that I can enter a complete booking in one place; and as a customer, I want the new fields available when I book online.

#### Acceptance Criteria

1. THE Admin_Panel SHALL expose the same field set on the admin booking create form and the admin Edit_Form, comprising cake, Cake_Weight, decor and combo Add_On selections with Quantity, LED_Name, occasion, booking name, booking date, plan, name-on-cake, number of guests, slot, special-person name, phone (required), email (optional), message, and the Money_Fields (food, other, cleaning, discount).
2. THE customer web booking flow SHALL expose, on its create form, cake with Cake_Weight, decor and combo Add_On selections with Quantity, LED_Name, and Combo selection as a distinct line.
3. THE customer web booking flow SHALL NOT expose the admin-only Money_Fields (food, other, cleaning, discount) on its create form.
4. WHEN the customer submits a create booking, THE customer web booking flow SHALL send the cake identifier, Cake_Weight, decor and combo identifiers with Quantity, and LED_Name text, and SHALL NOT send any computed price or any Money_Field.

### Requirement 18: Transparent combo line in all booking UIs

**User Story:** As a customer or admin, I want each selected combo shown as its own line with its price, so that the bundle cost is transparent before I confirm.

#### Acceptance Criteria

1. THE Admin_Panel SHALL display each selected Combo as a distinct line showing the combo name and its computed Combo_Line_Price in the live summary on both the admin create form and the admin Edit_Form.
2. THE customer web booking flow SHALL display each selected Combo as a distinct line showing the combo name and its computed Combo_Line_Price in the summary on the customer create form.
3. WHEN a Price_Breakdown is returned, THE Admin_Panel and the customer web booking flow SHALL render each selected Combo's name and amount as a separate line, not merged with special-decor add-ons.

### Requirement 19: Admin coupon management

**User Story:** As an admin, I want to create and edit coupons as location-scoped entities, so that I can offer flat or percentage discounts under controlled conditions.

#### Acceptance Criteria

1. WHEN an admin creates a Coupon, THE Booking_API SHALL store the Coupon's code, Coupon_Type (`flat` or `percentage`), value, optional Coupon_Cap, Coupon_Percentage_Base configuration (including the selected component subset when the base is `selected_components`), enabled Coupon_Limits and their thresholds, validity window, active flag, and location identifier.
2. WHEN an admin edits a Coupon, THE Booking_API SHALL update the Coupon's code, Coupon_Type, value, Coupon_Cap, Coupon_Percentage_Base configuration, enabled Coupon_Limits and thresholds, validity window, and active flag.
3. THE Booking_API SHALL scope every Coupon to a single location and SHALL allow an admin to create multiple Coupons per location.
4. THE Booking_API SHALL require role `admin` for creating and editing a Coupon.
5. IF a non-admin user requests to create or edit a Coupon, THEN THE Booking_API SHALL return a `403` error.
6. IF a submitted `percentage` Coupon has a percentage value below `0` or above `100`, or a present Coupon_Cap below `0`, or a `flat` Coupon value below `0`, THEN THE Booking_API SHALL return a `422` error with code `VALIDATION_ERROR` and SHALL NOT persist any change.
7. THE Booking_API SHALL add the `coupons` table (location-scoped: code, type, value, cap, percentage-base configuration, limit configuration, validity window, active flag) through an Alembic migration.

### Requirement 20: Apply a coupon on a booking

**User Story:** As a customer or admin, I want to apply a coupon code to a booking, so that the eligible discount is deducted from the total.

#### Acceptance Criteria

1. THE Admin_Panel SHALL present a coupon-code input on the admin create form and the admin Edit_Form, and the customer web booking flow SHALL present a coupon-code input on its create form.
2. WHEN a coupon code is submitted with a booking or preview, THE Booking_API SHALL validate the Coupon against the booking's location, the Coupon's active flag, the validity window, and every enabled Coupon_Limit before applying any discount.
3. WHEN a submitted Coupon is valid, THE Pricing_Service SHALL compute the Coupon_Discount as the flat value for a `flat` Coupon, or `min(Coupon_Cap, round(pct × configured_base_paise))` for a `percentage` Coupon, where the base is the pre-coupon total for base `total` or the admin-configured component subset for base `selected_components`.
4. THE Pricing_Service SHALL compute the total as `subtotal + food + other + cleaning − Admin_Manual_Discount − Coupon_Discount` and SHALL clamp the total at `0` so a Coupon can never make the total negative.
5. THE Pricing_Service SHALL apply the Coupon_Discount independently of and in addition to the Admin_Manual_Discount, without changing the existing Admin_Manual_Discount clamping behavior.
6. WHEN a booking or edit with a valid Coupon is persisted, THE Booking_Service SHALL persist the applied coupon code snapshot and the computed Coupon_Discount in paise on the booking.
7. WHEN the booking detail is returned, THE Booking_API SHALL return the applied coupon code and Coupon_Discount, and THE Edit_Form SHALL pre-fill the applied coupon code.
8. WHEN a Price_Breakdown is returned, THE Admin_Panel and the customer web booking flow SHALL display the Coupon_Discount as a distinct line showing the coupon code and amount.
9. WHEN the Booking_API receives any client-sent coupon amount, THE Booking_API SHALL ignore it and use the server-computed Coupon_Discount.

### Requirement 21: Coupon validation and limit enforcement

**User Story:** As the system owner, I want coupons rejected when they are invalid or exhausted, so that discounts apply only under the configured conditions.

#### Acceptance Criteria

1. IF a submitted coupon code does not match any Coupon for the booking's location, THEN THE Booking_API SHALL return a `422` error with code `COUPON_INVALID` and SHALL NOT persist any change.
2. IF a submitted Coupon is inactive or outside its validity window, THEN THE Booking_API SHALL return a `422` error with code `COUPON_INVALID` and SHALL NOT persist any change.
3. IF applying a submitted Coupon would violate an enabled Coupon_Limit (minimum order value not met, one-time use already used, total usage count exhausted, or per-customer usage limit exceeded, where the per-customer limit is counted against the booking's Normalized_Phone), THEN THE Booking_API SHALL return a `422` error with code `COUPON_NOT_APPLICABLE` and a descriptive message and SHALL NOT persist any change.
4. THE Booking_API SHALL track Coupon usage sufficiently to enforce the one-time-use, total-usage-count, and per-customer usage limits, counting the per-customer usage limit against the booking's Normalized_Phone, through an Alembic migration that adds the applied-coupon reference on the booking (code snapshot and computed Coupon_Discount in paise) and any usage-tracking required for those limits.
5. WHEN a Coupon is applied within all enabled limits, THE Booking_Service SHALL record the usage so that subsequent limit checks reflect it, keying any per-customer usage against the booking's Normalized_Phone.

### Requirement 22: Mandatory phone, optional email

**User Story:** As the system owner, I want every booking to carry a phone number and to treat email as optional, so that phone can serve as the customer identity for coupons and contact.

#### Acceptance Criteria

1. THE admin booking create form, THE Edit_Form, and THE customer web create form SHALL require a phone number and SHALL treat email as an optional field.
2. IF a submitted booking create or edit has a missing or blank phone number, THEN THE Booking_API SHALL return a `422` error with code `VALIDATION_ERROR` and SHALL NOT persist any change.
3. WHEN a submitted booking create or edit has no email, THE Booking_API SHALL accept the booking and SHALL persist a null email.
4. THE Booking_API SHALL make the booking email column nullable and SHALL make the phone a required booking field through an Alembic migration.
5. WHERE existing booking rows may have a null phone, THE Alembic migration SHALL handle the phone-required change without a hard database `NOT NULL` constraint that would fail on those rows, enforcing phone-required at the API/schema layer and either keeping the phone column nullable at the database level or backfilling existing rows; the design document resolves the exact strategy.
6. THE Admin_Panel and THE customer web booking flow SHALL mirror the phone-required and email-optional rules in their zod form schemas.

### Requirement 23: Indian mobile phone normalization

**User Story:** As the system owner, I want phone numbers normalized to a canonical Indian-mobile form, so that the same customer is recognized regardless of how the number is typed and coupon per-customer limits count correctly.

#### Acceptance Criteria

1. WHEN a phone number is submitted on a booking create or edit, THE Booking_API SHALL normalize it by stripping spaces and dashes, accepting a leading `0`, a `+91` country code, or no country code (defaulting the country code to `+91`), and reducing it to the canonical last 10 digits (the Normalized_Phone).
2. THE Booking_API SHALL treat a Normalized_Phone of exactly 10 digits beginning with `6`, `7`, `8`, or `9` as a valid Indian mobile number.
3. IF a submitted phone number does not normalize to a valid Indian mobile number, THEN THE Booking_API SHALL return a `422` error with code `VALIDATION_ERROR` and SHALL NOT persist any change.
4. THE Booking_API SHALL normalize `"+91 98765 43210"`, `"098765 43210"`, and `"9876543210"` to the same Normalized_Phone (`9876543210`).
5. THE Booking_API SHALL count the coupon per-customer usage limit against the Normalized_Phone, so that submissions differing only in phone-number formatting are treated as the same customer.

### Requirement 24: Record payments from the Edit_Form

**User Story:** As an admin or staff member, I want to record one or more payments against a booking from the Edit_Form, so that the booking's payment history and derived amounts reflect every advance and settlement received.

#### Acceptance Criteria

1. THE Edit_Form SHALL present a control to record a payment against the booking, capturing a method (`cash`, `upi`, `card`, or `other`), an amount in paise, and an optional note.
2. WHEN a user records a payment, THE Booking_API SHALL append one Payment_Entry to the `payments` ledger with the submitted method, amount, optional note, the received timestamp, and the recording user identifier.
3. THE Booking_API SHALL allow a booking to accumulate multiple Payment_Entry rows over time, so that an advance and later partial settlements each add a distinct ledger row.
4. WHEN a payment is recorded, THE Booking_API SHALL write a `payment_recorded` audit event recording the method and amount in paise.
5. THE Booking_API SHALL permit payment recording for role `admin` and role `staff`, restricting a Staff_User to bookings within the Staff_User's assigned location(s) and returning a `403` error for any other location, consistent with the existing payments endpoint.
6. WHEN the Edit_Form loads a booking, THE Edit_Form SHALL display the booking's full payment history oldest-first, showing each Payment_Entry's amount, method, received timestamp, and recording user, together with the derived Amount_Paid and Amount_Due.
7. THE Booking_API SHALL derive Amount_Paid as the sum of all Payment_Entry amounts in paise and Amount_Due as `total_paise − Amount_Paid`, and SHALL NOT store either value.
8. WHERE a booking is overpaid, THE Booking_API SHALL compute a negative Amount_Due and THE Edit_Form SHALL display the negative Amount_Due rather than clamping it to zero.
9. IF a submitted payment amount is not a positive integer number of paise, THEN THE Booking_API SHALL return a `422` error with code `VALIDATION_ERROR` and SHALL NOT append any Payment_Entry.

### Requirement 25: Void a payment via a reversing ledger entry

**User Story:** As an admin, I want to void a wrong payment by inserting a reversing entry, so that the ledger corrects itself without ever deleting or mutating the original record.

#### Acceptance Criteria

1. WHEN an admin voids a Payment_Entry, THE Booking_API SHALL insert a Reversing_Entry: a new `payments` row whose amount in paise is the negation of the original Payment_Entry's amount and whose `reverses_payment_id` references the original Payment_Entry.
2. WHEN a Reversing_Entry is inserted, THE Booking_API SHALL leave the original Payment_Entry row unchanged and SHALL NOT delete it, preserving the append-only audit trail.
3. WHEN a Payment_Entry is voided, THE Booking_API SHALL re-derive Amount_Paid as `SUM(amount_paise)` so that the Reversing_Entry nets the voided payment to zero effect.
4. THE Booking_API SHALL require role `admin` to void a payment.
5. IF a non-admin user requests to void a payment, THEN THE Booking_API SHALL return a `403` error and SHALL NOT insert any Reversing_Entry.
6. IF a user requests to void a Payment_Entry that has already been voided, THEN THE Booking_API SHALL return a `422` error with code `PAYMENT_ALREADY_VOIDED` and SHALL NOT insert any Reversing_Entry.
7. IF a user requests to void a Reversing_Entry, THEN THE Booking_API SHALL return a `422` error with code `PAYMENT_NOT_VOIDABLE` and SHALL NOT insert any Reversing_Entry.
8. IF a void request has a missing or blank reason, THEN THE Booking_API SHALL return a `422` error with code `VALIDATION_ERROR` and SHALL NOT insert any Reversing_Entry.
9. WHEN an admin voids a Payment_Entry, THE Booking_API SHALL write a `payment_voided` audit event recording the original Payment_Entry identifier, the Reversing_Entry, the acting admin, and the reason.
10. WHEN the Edit_Form loads a booking that has a Voided_Payment, THE Edit_Form SHALL display the original Payment_Entry marked voided and its Reversing_Entry in the payment history.

### Requirement 26: Payment void schema and migrations

**User Story:** As the system owner, I want the payment and audit schema extended to support reversing entries, so that voiding is persisted correctly and the change can be rolled back.

#### Acceptance Criteria

1. THE Booking_API SHALL relax the `payments` amount check constraint from `amount_paise > 0` to `amount_paise <> 0` through an Alembic migration, so that a negative Reversing_Entry amount is permitted while a zero amount remains rejected.
2. THE Booking_API SHALL add a nullable `reverses_payment_id` column to the `payments` table as a self-referencing foreign key to `payments.id` through an Alembic migration.
3. THE Booking_API SHALL add `payment_voided` to the `booking_events` allowed event-type check-constraint list through an Alembic migration.
4. THE Alembic migrations for the amount-check relaxation, the `reverses_payment_id` column, and the `payment_voided` event type SHALL each be reversible.

## Test Cases

Per the steering docs, this feature touches money and access control, so the following cases are enumerated explicitly and are required before the change is considered done.

### Pricing (server-side, in `services/pricing.py`)

- Add_On amount equals unit price × quantity for decor and combo lines.
- A quantity of `1` reproduces the pre-quantity single-line price (backward compatibility).
- Subtotal equals plan price + extra-guest charge + sum of Add_On amounts, with quantities applied.
- Total equals subtotal + food + other + cleaning − discount.
- Admin discount is clamped to `[0, plan.max_discount_paise]` and forced to `0` when `give_discount` is false.
- Any client-sent total is ignored; the Price_Breakdown comes only from validated catalog rows and quantities.
- Round-trip/consistency: the Preview_Endpoint breakdown for a given input equals the breakdown persisted when that same input is submitted (preview matches save).

### Add-on quantity math and data model

- Quantity `< 1` or non-integer is rejected with `422`.
- Multiple units of the same decor/combo produce one Add_On_Line with the correct quantity and multiplied amount.
- Cake lines always persist quantity `1`.
- The Alembic migration backfills existing `booking_items` rows with quantity `1` and is reversible.

### Cake weight pricing (server-side, in `services/pricing.py`)

- Cake line price equals base × 1 at 0.5 kg, base × 2 at 1.0 kg, and base × 3 at 1.5 kg.
- A Cake_Weight that is not a positive multiple of 0.5 kg (e.g. 0.3 kg, 0.75 kg, 0 kg, negative) is rejected with `422` `VALIDATION_ERROR` and persists nothing.
- The chosen Cake_Weight is persisted on the cake Add_On_Line in half-kg units and is pre-filled on the Edit_Form.
- The Alembic migration backfills existing cake lines with 0.5 kg and is reversible.
- Cake_Weight pricing applies identically in the customer web booking flow and the admin booking flow.
- The client never sends a computed cake price; only the cake identifier and Cake_Weight are sent, and any client-sent cake price is ignored.

### Combo authoring and access control

- An admin creates a Combo with just a name and a combo price (no component list), scoped to the acting location; optional Combo_Cake_Baseline and Combo_LED_Baseline may each be present or absent.
- A Combo with a negative combo price, a present negative Combo_Cake_Baseline, or a present negative Combo_LED_Baseline is rejected with `422` `VALIDATION_ERROR` and persists nothing.
- A Combo with a combo price of `0` and both baselines absent is accepted (no component list is required).
- An admin may create multiple Combos for a single location.
- A non-admin (staff or customer) request to create or edit a Combo returns `403`.
- The Alembic migration adding the Combo_Cake_Baseline and Combo_LED_Baseline columns to the combos table is reversible.

### Combo delta pricing (server-side, in `services/pricing.py`)

- Combo_Line_Price equals combo price plus the floored cake-upgrade delta (when a cake baseline is present) plus the floored LED-upgrade delta (when an LED baseline is present).
- At the cake baseline (chosen weighted cake price equals Combo_Cake_Baseline), the cake delta is `0`; at the LED baseline (`LED_Letter_Count × 4000` equals Combo_LED_Baseline), the LED delta is `0`.
- A cheaper chosen cake (weighted price below baseline) floors the cake delta at `0`; a shorter LED name (below the LED baseline) floors the LED delta at `0`; the line never drops below the combo price.
- The Cake_Weight multiplier is applied before subtracting the cake baseline (weight-before-delta).
- A selected Combo is always treated as quantity `1`.
- When a Combo with a cake baseline is selected, the chosen cake is priced only through the combo cake-delta and no separate standalone weighted cake line is emitted; when no such Combo is selected, the chosen cake is a standalone weighted line.
- When a Combo with an LED baseline is selected, LED is priced only through the combo LED-delta and no separate standalone LED line is emitted; when no such Combo is selected, LED is a standalone line of `LED_Letter_Count × 4000` paise.
- Real combo examples (paise): Combo1 (`70000`, LED baseline `20000`) with LED_Name "ARUNA" (5) → `70000`; with "SANJAY" (6) → `74000`. Combo3 (`110000`, cake baseline `40000`, LED baseline `20000`) with chosen cake base `50000` at 0.5 kg and LED_Name "ARUNA" → `120000`; same cake at 1.0 kg → `170000`.
- The client sends only the Combo identifier plus the chosen cake identifier, Cake_Weight, and LED_Name text; any client-sent Combo_Line_Price, Cake_Upgrade_Delta, or LED_Upgrade_Delta is ignored.
- Round-trip/consistency: the Preview_Endpoint breakdown equals the persisted breakdown for the same input, including the chosen Cake_Weight, LED_Name, and the Combo deltas (preview matches save).

### LED letters pricing (server-side, in `services/pricing.py`)

- LED_Letter_Count counts only alphabetic A–Z characters, is case-insensitive, and ignores spaces and punctuation (e.g. "HAPPY BIRTHDAY" = 13, "ARUNA" = 5, "SANJAY" = 6).
- A standalone LED line (no Combo covers LED) equals `LED_Letter_Count × 4000` paise.
- An empty or absent LED_Name yields LED_Letter_Count `0` and no LED charge.
- When a Combo with an LED baseline is selected, LED is priced through the combo LED-delta and no standalone LED line is emitted.
- The LED_Unit_Price `4000` paise/letter is referenced from a single documented constant, not hardcoded in multiple places.
- The LED_Name is persisted on the booking and pre-filled on the Edit_Form in both the admin and customer flows.
- The client sends only the LED_Name text; any client-sent LED line price or LED_Letter_Count is ignored.
- The Alembic migration adding the LED_Name column to the bookings table is reversible.

### Create/edit field parity

- The admin create form and the admin Edit_Form expose an identical field set (cake, Cake_Weight, decor/combo selections with quantity, LED_Name, occasion, booking name, date, plan, name-on-cake, guests, slot, special-person name, phone, message, and the Money_Fields).
- The customer web create form exposes cake + Cake_Weight, decor/combo quantities, LED_Name, and combo selection as a distinct line, and does not expose the admin-only Money_Fields (food, other, cleaning, discount).
- A customer create submission sends only identifiers, quantities, Cake_Weight, LED_Name text, and (optionally) a coupon code; any Money_Field or computed price in a customer submission is ignored.

### Combo transparency in booking UIs

- Each selected Combo appears as a distinct line with the combo name and its computed Combo_Line_Price in the admin create summary, the admin Edit_Form summary, and the customer create summary.
- A selected Combo line is rendered separately from special-decor add-on lines in both the admin and customer summaries.

### Contact fields and phone normalization (phone required, email optional)

- A booking create or edit with a missing or blank phone is rejected with `422` `VALIDATION_ERROR` and persists nothing.
- A booking create or edit with no email is accepted and persists a null email.
- The admin create form, the admin Edit_Form, and the customer web create form each require phone and treat email as optional (zod schemas mirror the API).
- Phone normalization equivalence: `"+91 98765 43210"`, `"098765 43210"`, and `"9876543210"` all normalize to `9876543210` and count as the same customer for the coupon per-customer usage limit.
- An invalid Indian mobile number (fewer or more than 10 significant digits, or a 10-digit number not starting with `6`–`9`, e.g. `"12345"`, `"5876543210"`, `"98765 4321"`) is rejected with `422` `VALIDATION_ERROR` and persists nothing.
- The booking email column is nullable after migration, and the phone-required change does not fail on existing rows that may have a null phone (reversible migration).

### Role and location access control

- Unauthenticated request to edit detail / preview / submit returns `401`.
- A non-admin, non-staff role returns `403`.
- A Staff_User editing a booking in their own location succeeds.
- A Staff_User editing a booking outside their location returns `403`.
- An Admin_User may edit bookings across all locations.

### Slot conflict on plan/slot/date change

- Editing plan/slot/date into a slot already held by another active booking returns `409` "Slot not available" and persists nothing.
- Editing a booking without changing plan/slot/date does not self-conflict.
- Editing other fields (money, customer details) while keeping the slot does not trigger a conflict.

### Editable-status rules

- Editing a `pending` or `accepted` booking succeeds.
- Editing a `rejected` or `expired` booking returns `422` and persists nothing.

### Ledger / amount-due display

- The Edit_Form and preview show Amount_Paid as the derived sum of recorded payments.
- Amount_Due equals `total_paise − Amount_Paid` and reflects the recomputed total after an edit.
- Amount_Due may be negative (overpaid) and is displayed as such, never clamped silently.

### Audit

- A persisted edit writes exactly one `edited` booking event with the old and new money snapshot and the acting user.

### Coupon pricing (server-side, in `services/pricing.py`)

- A `flat` coupon reduces the total by its fixed paise value.
- A `percentage` coupon on base `total` applies the percentage to the pre-coupon total (`subtotal + food + other + cleaning − Admin_Manual_Discount`).
- A `percentage` coupon on base `selected_components` applies the percentage only to the admin-configured subset: verify a plan-price-only base, an add-ons+combos base, and a cake-included base each compute from exactly those components.
- A `percentage` coupon's discount is clamped by the Coupon_Cap when present and uncapped when the cap is nil.
- The Coupon_Discount stacks with the Admin_Manual_Discount: both reduce the total, applied as `… − Admin_Manual_Discount − Coupon_Discount`, and the Admin_Manual_Discount clamping is unchanged.
- The total is clamped at `0`: a coupon larger than the remaining total yields a total of `0`, never negative.
- Round-trip/consistency: the Preview_Endpoint breakdown equals the persisted breakdown for the same input including the applied coupon (preview matches save).
- The client sends only the coupon code; any client-sent coupon amount is ignored and the server-computed Coupon_Discount is used.

### Coupon validation and limit enforcement

- An unknown coupon code (no match for the booking's location) returns `422` `COUPON_INVALID` and persists nothing.
- An inactive coupon or a coupon outside its validity window returns `422` `COUPON_INVALID` and persists nothing.
- A coupon whose minimum-order-value limit is not met returns `422` `COUPON_NOT_APPLICABLE` and persists nothing.
- A one-time-use coupon already used returns `422` `COUPON_NOT_APPLICABLE` and persists nothing.
- A coupon whose total usage count is exhausted returns `422` `COUPON_NOT_APPLICABLE` and persists nothing.
- A coupon whose per-customer usage limit (counted against the booking's Normalized_Phone) is exceeded returns `422` `COUPON_NOT_APPLICABLE` and persists nothing.
- The per-customer usage limit is keyed on the Normalized_Phone: the same customer applying the coupon under different phone-number formats (`"+91 98765 43210"`, `"098765 43210"`, `"9876543210"`) counts as one customer toward the limit.
- A coupon from a different location than the booking is rejected (location mismatch) and persists nothing.
- Admin coupon management is admin-only: a non-admin (staff or customer) create/edit request returns `403`.
- Applying a `percentage` coupon with a value out of range (below `0` or above `100`) at authoring returns `422` `VALIDATION_ERROR` and persists nothing.
- Applying a valid coupon within all enabled limits records usage so subsequent one-time/total-usage/per-customer checks reflect it.
- The applied coupon code and computed Coupon_Discount are persisted on the booking and pre-filled on the Edit_Form.
- The Alembic migrations for the `coupons` table and the booking's applied-coupon reference (code snapshot + Coupon_Discount paise) and usage tracking are reversible.

### Payments (ledger recording and voiding)

- Recording multiple partial payments of different methods appends one Payment_Entry per payment and Amount_Paid equals the sum of their amounts in paise (e.g. ₹500 UPI + ₹2000 card + ₹1500 cash → Amount_Paid `400000` paise).
- Amount_Due reflects the derived `total − Amount_Paid` after a partial payment and after a full payment, and can go negative on overpayment (overpaid bookings display a negative Amount_Due, never clamped).
- A recorded payment amount that is not a positive integer paise value is rejected with `422` `VALIDATION_ERROR` and appends nothing.
- Payment recording is allowed for admin and for staff within their own location; a Staff_User recording against a booking outside their location returns `403`.
- Each recorded payment writes exactly one `payment_recorded` audit event with the method and amount.
- Voiding a Payment_Entry inserts a Reversing_Entry with a negative amount equal to the negation of the original amount and a `reverses_payment_id` referencing the original; Amount_Paid nets correctly (the voided payment contributes zero) while the original row remains present in the ledger.
- Voiding is admin-only: a staff void request returns `403` and persists nothing.
- A payment may be voided at most once: a second void of the same Payment_Entry returns `422` `PAYMENT_ALREADY_VOIDED` and persists nothing.
- A Reversing_Entry cannot be voided: a void request against a reversal row returns `422` `PAYMENT_NOT_VOIDABLE` and persists nothing.
- A void with a missing or blank reason returns `422` `VALIDATION_ERROR` and persists nothing.
- A persisted void writes exactly one `payment_voided` audit event recording the original Payment_Entry id, the Reversing_Entry, the acting admin, and the reason.
- The Edit_Form shows the full payment history oldest-first (amount, method, received timestamp, recording user) plus derived Amount_Paid and Amount_Due, and shows voided payments marked voided alongside their Reversing_Entry.
- Amount_Paid and Amount_Due are always derived from the ledger (`Amount_Paid = SUM(amount_paise)`, `Amount_Due = total − Amount_Paid`) and never stored.
- The Alembic migration relaxing the `payments` amount check from `amount_paise > 0` to `amount_paise <> 0` is reversible, and after it a negative Reversing_Entry amount is accepted while a zero amount is still rejected.
- The Alembic migration adding the nullable self-referencing `reverses_payment_id` FK to `payments` is reversible.
- The Alembic migration adding `payment_voided` to the `booking_events` allowed event-type check constraint is reversible.
