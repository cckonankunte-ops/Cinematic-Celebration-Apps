# Implementation Plan — Combo Savings & Add-ons Layout

- [x] 1. Add `compare_at_paise` to the combo model + migration
  - Add nullable `compare_at_paise: Mapped[int | None]` (BigInteger) to `ComboItem` in `apps/api/app/models/combo_item.py`.
  - Add `CheckConstraint("compare_at_paise IS NULL OR compare_at_paise >= 0", name="ck_combo_items_compare_at_nonneg")`.
  - Create Alembic migration `apps/api/alembic/versions/0014_add_compare_at_paise_to_combo_items.py` (down_revision `0013`): add column + check constraint; downgrade drops both.
  - _Requirements: 1, 5_

- [x] 2. Server-side savings helper + public combo read
  - [x] 2.1 Add `combo_savings_paise(price_paise, compare_at_paise) -> int` helper in `apps/api/app/services/catalog.py` returning `max(0, worth - price)`, `0` when worth is None.
    - _Requirements: 1_
  - [x] 2.2 Add `worth_paise: int | None = None` and `savings_paise: int = 0` to `ComboRead` in `apps/api/app/schemas/catalog.py`; populate both in `catalog.list_combos(...)` using the helper (keep existing `image_url` via `public_url`).
    - _Requirements: 1, 2, 4_
  - [x] 2.3 Write/extend tests: unit tests for the helper (worth>price, worth==price, worth<price, worth None, never-negative property); integration test that the public combos endpoint returns correct `worth_paise`/`savings_paise` for seeded combos with and without worth, and for a no-baseline combo.
    - _Requirements: 1, 4; Mandatory test cases 1, 3, 4_

- [x] 3. Admin combo worth: schemas + service
  - [x] 3.1 Add `compare_at_paise: int | None = Field(default=None, ge=0)` to `ComboCreate` and `ComboUpdate`; add `compare_at_paise: int | None` and derived `savings_paise: int` to `ComboAdminRead` in `apps/api/app/schemas/catalog_admin.py`.
    - _Requirements: 5_
  - [x] 3.2 Persist `compare_at_paise` on create/update in `apps/api/app/services/catalog_admin.py`; populate `compare_at_paise`/`savings_paise` in the admin read builder (reuse the helper from 2.1).
    - _Requirements: 5_
  - [x] 3.3 Tests: admin create/update sets `compare_at_paise` and the public response reflects the new `worth_paise`/`savings_paise`; `ge=0` validation rejects negatives; staff cannot set worth on a combo outside their assigned location(s).
    - _Requirements: 5; Mandatory test cases 5, 7_

- [x] 4. Assert booking-charge invariance (no pricing change)
  - Add/extend an integration test proving the charged subtotal/total for a combo selection is identical whether `compare_at_paise` is set or unset, and that a booking request carrying `worth_paise`/`savings_paise`/totals is ignored (charge computed from IDs/quantities only).
  - Confirm `services/pricing.py` combo math is untouched.
  - _Requirements: 1, 4; Mandatory test cases 2, 6_

- [x] 5. Regenerate API types + web combo type
  - Regenerate `apps/admin/src/api/schema.ts` and the web OpenAPI types (`openapi-typescript`).
  - Update the hand-written `Combo` type in `apps/web/src/lib/api.ts` to add `worth_paise: number | null` and `savings_paise: number`. No client-side savings math.
  - _Requirements: 1, 2_

- [x] 6. Admin UI: combo worth input + savings preview
  - In `apps/admin/src/features/catalog/` combo create/edit form, add an optional "Worth / compare-at (₹)" input (rupees → paise on submit, matching existing money inputs); blank = unset.
  - Show a read-only "Saves ₹X" preview next to the price from the server-provided `savings_paise`.
  - _Requirements: 5_

- [x] 7. Customer wizard: combo hero cards above collapsible add-ons
  - [x] 7.1 In `apps/web/src/components/booking/`, render combos as image-forward hero cards ABOVE the individual add-ons: combo image (festive placeholder fallback), name, description, price; strike-through `worth_paise` and a "Save ₹X" badge ONLY when `savings_paise > 0`. Rupee formatting via the existing money formatter.
    - _Requirements: 2, 3, 4_
  - [x] 7.2 Convert cakes/special-decor into image-forward cards inside native `<details>`/`<summary>` collapsible sections (collapsed by default, independent expand); remove the nested inner scroll box. Keep the "representation only / colours subject to availability / prices inclusive of taxes" note near the add-ons.
    - _Requirements: 2, 3_
  - [x] 7.3 Preserve all selection/quantity behaviour and the live server-computed total; CSS-only styling (festive palette, reduced-motion safe), no new dependency; verify usable at 360px.
    - _Requirements: 2, 3, 4_
  - [x] 7.4 Update/add vitest: hero card shows strike-through + "Save ₹X" when `savings_paise > 0`; shows price only when `savings_paise === 0`; add-on sections render collapsed with no nested scroll container; update the existing booking-wizard test for the new layout.
    - _Requirements: 2, 3; Mandatory test cases 8, 9, 10_

- [x] 8. Verify, lint, and wire-up
  - Run `ruff` + `pytest` (API, real Postgres) and `eslint` + `vitest` (admin + web) until clean.
  - Confirm the booking page JS bundle stays within the lean target (< 150 KB gzipped).
  - Update `.env.example`/docs only if configuration changed (none expected).
  - _Requirements: 1, 2, 3, 4, 5_
