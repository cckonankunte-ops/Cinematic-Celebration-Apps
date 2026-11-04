# Requirements — Combo Savings & Add-ons Layout

## Introduction

Cinematic Celebration sells "combos" as savings bundles (e.g. COMBO-1 = Single Fog
Entry + ½kg Cake, marketed as "₹1000 → ₹700, Save ₹300"; "Save up to ₹800 with
Combos"). A combo is built by combining special-decor items, sometimes plus a cake.

In the current customer booking wizard, Combos and the individual add-ons (cakes,
special decor) are shown in separate places, so a customer can't easily see the
savings advantage of picking a combo. This feature makes combos prominent and
adjacent to the individual add-ons — image-forward hero cards shown above the add-on
grid, each with a strike-through "worth" price and a "Save ₹X" badge that mirrors the
WhatsApp add-ons banner — and reworks the add-ons area to be mobile-first (image
cards in collapsible sections, no nested scroll box).

This is primarily a presentation change plus one small catalog-data addition: a
server-provided "worth"/compare-at amount per combo so the savings figure can be
displayed. Combos are already a first-class catalog type with server-authoritative
pricing (including cake/LED absorption); that pricing math is NOT changed here.

### Steering-derived constraints (apply to every requirement)

- All money is integer paise. The UI converts to rupees for display only.
- Pricing and any savings figure are **server-authoritative** (`services/pricing.py`
  / catalog services). The client sends only IDs and quantities and **never** sends
  or computes money, including the "worth" or "savings".
- The booking page JS bundle stays lean (target < 150 KB gzipped). Styling is
  CSS-only; no new animation or UI library is added.
- No payment-gateway work (Phase 1 is manual advance).

---

## Requirement 1 — Server-provided, server-authoritative combo savings

**User story:** As a customer, I want to see how much a combo saves me versus buying
the parts, so that I can see the value of choosing a combo — and as the business, I
need that savings figure to be computed on the server so it can't be manipulated by
the client.

### Acceptance Criteria

1. WHEN the public API returns a combo THEN it SHALL include the combo's `price_paise`
   (the amount charged), a `worth_paise` (the compare-at / "original" amount), and a
   derived `savings_paise`.
2. THE system SHALL compute `savings_paise = max(0, worth_paise − price_paise)` on the
   server.
3. IF `worth_paise` is less than or equal to `price_paise` THEN `savings_paise` SHALL
   be 0 and the response SHALL NOT present a positive saving.
4. THE system SHALL ignore any `worth_paise`, `savings_paise`, or total sent by the
   client; booking pricing SHALL continue to use only server-side values.
5. THE displayed savings SHALL never be negative and SHALL never be fabricated (if no
   worth is configured, savings is 0 / absent).

---

## Requirement 2 — Combos displayed prominently beside the add-ons

**User story:** As a customer choosing add-ons, I want to see the combo bundles first
and clearly, so that I understand the saving before I pick individual items.

### Acceptance Criteria

1. WHEN the customer reaches the add-ons area of the booking wizard THEN the system
   SHALL display available combos as image-forward hero cards ABOVE the individual
   add-on grid (cakes, special decor).
2. WHERE a combo has a positive `savings_paise` THE combo card SHALL show the
   strike-through `worth_paise` next to the `price_paise` and a "Save ₹X" badge.
3. WHERE a combo has zero savings THE card SHALL show only the price (no strike-through,
   no "Save" badge).
4. THE combo card SHALL use the combo's existing image (`object_key` → public URL) and
   fall back to a festive placeholder when no image is available.
5. THE individual add-ons (cakes, special decor) SHALL be presented as image-forward
   cards grouped in collapsible sections, with NO nested inner scroll box.
6. Selecting, deselecting, and changing quantities of combos and add-ons SHALL continue
   to update the live booking total (which remains server-computed).

---

## Requirement 3 — Mobile-first presentation

**User story:** As a mostly-mobile audience arriving from an ad, I want the add-ons
step to be easy to use one-handed on a small screen, so that I don't abandon the
booking.

### Acceptance Criteria

1. THE combo and add-on cards SHALL be usable and readable at a 360px viewport width.
2. Collapsible add-on sections SHALL be collapsed to a short default so the step fits
   without a long scroll, expanding only the categories the customer opens.
3. THE styling SHALL be CSS-only (festive palette / existing utilities); no new
   animation or UI library SHALL be added.
4. THE change SHALL keep the booking page JS bundle within the project's lean target
   (< 150 KB gzipped).

---

## Requirement 4 — Combo composition display without changing pricing math

**User story:** As a customer, I want each combo card to show what's included, so that
I understand the bundle — without the app changing how combos are priced.

### Acceptance Criteria

1. THE combo card SHALL display the combo's name and description (which lists what's
   included, e.g. "Single Fog Entry + ½kg Cake").
2. WHERE a combo has a cake baseline and/or LED baseline THE pricing behaviour
   (base price + floored cake/LED upgrade deltas, cake/LED absorption) SHALL remain
   exactly as today.
3. WHERE a combo has no cake baseline and no LED baseline THE card SHALL still display
   correctly (name, description, price, image, savings if any).
4. THE feature SHALL NOT alter the computed booking subtotal/total for any existing
   combo selection (savings is display-only; it does not change what is charged).

---

## Requirement 5 — Admin control of the combo worth / compare-at value

**User story:** As an admin, I want to set and maintain each combo's "worth" value, so
that the displayed savings are accurate and under my control per location.

### Acceptance Criteria

1. WHEN an admin creates or edits a combo THEN the system SHALL allow setting the
   combo's worth / compare-at amount (entered in rupees in the UI, stored as integer
   paise).
2. THE worth value SHALL be validated as a non-negative integer (paise) on the server.
3. WHEN an admin updates a combo's worth THEN the public API response for that combo
   SHALL reflect the new `worth_paise` and recomputed `savings_paise`.
4. THE admin worth control SHALL respect existing role/location access rules (staff are
   limited to their assigned location(s); admins see all).
5. IF no worth is set for a combo THEN the combo SHALL display with zero savings (price
   only), not an error.

---

## Mandatory test cases (money / access)

Because this feature touches money display and admin control, the following SHALL be
covered by tests:

1. **Savings formula:** `savings_paise = max(0, worth_paise − price_paise)` computed
   server-side for representative combos.
2. **Client cannot inject money:** a booking request carrying `worth_paise` /
   `savings_paise` / totals is ignored; the server computes the charged total solely
   from IDs/quantities.
3. **No-baseline combo:** a combo with no cake and no LED baseline returns a correct
   response and renders (price + optional savings).
4. **Worth ≤ price:** savings is 0 and no "Save" badge / negative value is produced.
5. **Admin edit reflected:** updating a combo's worth changes `worth_paise` and
   `savings_paise` in the public API response.
6. **Pricing unchanged:** the charged subtotal/total for an existing combo selection is
   identical before and after this feature (savings is display-only).
7. **Access control:** a staff user cannot set the worth on a combo outside their
   assigned location(s).
