# Design — Combo Savings & Add-ons Layout

## Overview

This feature adds a server-provided "worth" (compare-at) amount to combos so the
customer booking wizard can show a strike-through price and a "Save ₹X" badge, and
reworks the wizard's add-ons area so combos appear as prominent image-forward hero
cards directly above the individual add-ons (cakes, special decor), which become
image cards in collapsible sections.

The savings figure is **display-only** and **server-authoritative**: the server stores
`compare_at_paise` per combo and returns `worth_paise` + a derived `savings_paise` in
the public combo payload. Nothing about how a combo is actually charged changes — the
existing `services/pricing.py` combo math (base + floored cake/LED upgrade deltas,
cake/LED absorption) is untouched.

### Design goals

- Savings computed on the server; client never sends worth/savings/totals.
- One small additive schema change (`combo_items.compare_at_paise`, nullable) via an
  Alembic migration; no change to any existing column or constraint semantics.
- Zero change to the charged subtotal/total for any existing combo selection.
- Frontend: CSS-only, no new dependency, bundle stays lean, usable at 360px.

---

## Data model

### `combo_items.compare_at_paise` (new, nullable)

| Column | Type | Null | Notes |
|---|---|---|---|
| `compare_at_paise` | `BigInteger` | yes | The combo's "worth" / original price in paise. NULL means no worth configured → zero savings. |

Constraint: `CheckConstraint("compare_at_paise IS NULL OR compare_at_paise >= 0", name="ck_combo_items_compare_at_nonneg")` — mirrors the existing baseline check-constraint naming.

Migration: `0014_add_compare_at_paise_to_combo_items.py` (add column + check constraint; downgrade drops both). Nullable, no default backfill — existing combos start with NULL (zero savings) until an admin sets a worth, which is the safe/honest default.

Why a stored compare-at rather than deriving worth from the included parts: a combo's
parts aren't modelled as explicit line references (the combo carries optional
`cake_baseline_paise` / `led_baseline_paise`, not a list of decor item IDs), so there
is no reliable server-side "sum of parts". A stored, admin-controlled worth matches how
the business already prints the banner (₹1000 → ₹700) and keeps the number accurate and
intentional. This is also the lowest-risk option (purely additive).

---

## Savings computation (server)

A single helper keeps the rule in one place:

```python
def combo_savings_paise(price_paise: int, compare_at_paise: int | None) -> int:
    """Display-only saving: max(0, worth - price). NULL worth => 0."""
    if compare_at_paise is None:
        return 0
    return max(0, compare_at_paise - price_paise)
```

- `worth_paise` returned to clients = `compare_at_paise` (may be `None`).
- `savings_paise` returned = `combo_savings_paise(price_paise, compare_at_paise)`.
- Rule guarantees: never negative; `worth <= price` ⇒ 0; NULL worth ⇒ 0.

This helper lives in `services/catalog.py` (read-side display concern), NOT in the
booking pricing path — the booking total is unaffected.

---

## API changes

### Public read schema `ComboRead` (`schemas/catalog.py`)

Add two fields:

```python
class ComboRead(BaseModel):
    id: int
    name: str
    description: str
    price_paise: int
    image_url: str
    worth_paise: int | None = None   # compare-at; None when unset
    savings_paise: int = 0           # max(0, worth - price); 0 when no worth
```

Populated in `catalog.list_combos(...)` using `public_url(object_key)` (already done
for `image_url`) and `combo_savings_paise(...)`. Endpoint
`GET /api/v1/public/locations/{location_id}/combos` is unchanged in shape/path.

### Admin schemas (`schemas/catalog_admin.py`)

- `ComboCreate`: add `compare_at_paise: int | None = Field(default=None, ge=0)`.
- `ComboUpdate`: add `compare_at_paise: int | None = Field(default=None, ge=0)`.
- `ComboAdminRead`: add `compare_at_paise: int | None` and (for convenience) a derived
  `savings_paise: int` so the admin UI can preview the saving it's configuring.

Validation (`ge=0`) enforces non-negative paise. Admin create/update flow and
role/location checks in `services/catalog_admin.py` are reused as-is; only the new field
is persisted.

### Booking path — explicitly unchanged

`ComboSelection` / the pricing request carry only the combo id (server loads the
`ComboItem`). No `worth`/`savings` is accepted on any booking request body. The charged
amount is computed exactly as today.

---

## Admin UI (`apps/admin/src/features/catalog/`)

- Add a "Worth / compare-at (₹)" input to the combo create/edit form (rupees in UI →
  paise on submit, matching existing money inputs). Optional; blank = NULL = no savings.
- Show a small read-only "Saves ₹X" preview next to the price in the combo form/list so
  staff can sanity-check the configured saving.
- No access-control change: the combo admin routes already enforce
  role/location via the router-level dependency; staff remain limited to their
  location(s).

---

## Customer wizard UI (`apps/web/src/components/booking/`)

The add-ons area (step 2 of the 3-step wizard) is restructured:

```
ADD-ONS (step 2)
┌─────────────────────────────────────────────┐
│  Save with Combos                             │  ← heading
│  ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│  │ [image]   │ │ [image]   │ │ [image]   │   │  ← combo hero cards
│  │ Combo-1   │ │ Combo-2   │ │ Combo-3   │   │
│  │ ₉̶₁̶₀̶₀̶₀̶ ₹700 │ │ ...       │ │ ...       │   │  ← strike-through worth + price
│  │ [Save ₹300]│ │           │ │           │   │  ← badge only when savings>0
│  └───────────┘ └───────────┘ └───────────┘   │
│                                               │
│  Add individual items                         │
│  ▸ Cakes            (collapsed by default)    │  ← <details>/<summary>, no inner scroll
│  ▸ Special Decor    (collapsed by default)    │
└─────────────────────────────────────────────┘
```

Implementation notes:
- Combo hero cards: reuse the existing combo data now carrying `worth_paise` /
  `savings_paise`. Render strike-through worth + price; render the "Save ₹X" badge
  **only** when `savings_paise > 0`. Rupee formatting via the existing money formatter.
- Image: combo `image_url` with the festive placeholder fallback already used for plan
  theme cards.
- Collapsible add-on sections: native `<details>`/`<summary>` (zero JS, zero bundle
  cost) or the existing disclosure pattern; each category expands independently; remove
  the current nested scroll box.
- Selection state, quantities, and the live server-computed total behave exactly as
  today; only layout/presentation changes.
- CSS-only styling with the festive palette; respects reduced-motion; no new library.
- Keep the "representation only / colours subject to availability / prices inclusive of
  taxes" note near the add-ons.

### TypeScript types

Regenerate `schema.ts` from OpenAPI (per project convention `openapi-typescript`); the
hand-written `apps/web/src/lib/api.ts` `Combo` type gains `worth_paise: number | null`
and `savings_paise: number`. No client-side savings math.

---

## Testing

Backend (pytest, real Postgres):
1. `combo_savings_paise` unit cases: `worth>price` ⇒ positive; `worth==price` and
   `worth<price` ⇒ 0; `worth is None` ⇒ 0; never negative (property-style over random
   price/worth).
2. Public combos endpoint returns correct `worth_paise`/`savings_paise` for seeded
   combos (with and without worth).
3. No-baseline combo (no cake/LED) returns a valid payload and renders fields.
4. Booking pricing invariance: charged subtotal/total for a combo selection is byte-for-
   byte identical before/after this change (worth set vs unset makes no difference to the
   charge).
5. Client injection: a booking request carrying `worth_paise`/`savings_paise`/totals is
   ignored; server computes the charge from IDs/quantities only.
6. Admin edit: updating `compare_at_paise` via the admin endpoint changes `worth_paise` +
   `savings_paise` in the public response.
7. Access control: a staff user cannot set `compare_at_paise` on a combo outside their
   assigned location(s) (reuses existing location-scope tests).

Frontend (vitest):
8. Combo hero card renders strike-through worth + "Save ₹X" when `savings_paise > 0`.
9. Combo card with `savings_paise === 0` renders price only (no strike-through, no badge).
10. Add-on sections render collapsed with no nested scroll container; existing wizard
    behaviour/test updated for the new layout.

---

## Risks & mitigations

- **Showing a wrong/old saving:** worth is admin-controlled and nullable; unset ⇒ no
  savings shown, so the honest default is "no claim". Admin preview reduces mis-entry.
- **Bundle growth:** native `<details>` + existing formatters means no new dependency;
  verify bundle stays under target.
- **Booking-flow regression:** the feature is display-only on the pricing side; test #4
  asserts charge invariance, and the existing wizard test is updated rather than removed.
```

