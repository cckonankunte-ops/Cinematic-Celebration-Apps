# Future Work / Deferred Items

Operational and product items we've consciously deferred. Not bugs; recorded so
they aren't forgotten. Revisit when data volume or need actually warrants.

## R2 orphaned-image cleanup (reconcile job)

**Context.** Catalog images (cakes, special decor, combos, plan gallery) are
stored in Cloudflare R2; the DB stores only the object key. "Deactivate" on a
catalog item is a **soft delete** (`is_active = false`, `effective_to = today`)
and intentionally does NOT delete the R2 object — historical bookings reference
these items and must keep rendering. Editing an item to replace its image
uploads a new object and leaves the old one orphaned. Removing a plan gallery
image deletes the DB row but not the R2 object.

**Concern.** Over months/years, orphaned objects accumulate and grow storage.

**Cost reality (why it's deferred).** R2 storage ≈ **$0.015 / GB / month** with
**no egress fees**. At this catalog's scale (tens–hundreds of items, ~300 KB
each), even 10,000 orphans ≈ 3 GB ≈ ~$0.05/month — negligible against the
<$7/month infra target. Not worth building until churn is materially higher.

**Proposed solution (when needed).** A safe, reference-checked reconcile job,
run by cron like `expire_pending` (no new infrastructure):
1. Collect every object key referenced by a live row: `cakes.object_key`,
   `special_decor_items.object_key`, `combo_items.object_key`,
   `plan_gallery_images.object_key`, plus any booking snapshot that stores a key.
2. List objects in the R2 public bucket.
3. Delete only objects that are **both** (a) unreferenced AND (b) older than a
   safety window (e.g. 90 days) so an object uploaded mid-edit is never caught.
   Idempotent; dry-run/report mode first.

**Risks to respect.** Never delete an object still referenced by any live row or
historical booking. Prefer an explicit allowlist of prefixes
(`cakes/`, `special-decor/`, `combos/`, `plans/`) and the age guard.

**Status:** deferred (recorded 2026). Not scheduled.

## Multi-tenant SaaS / leasing the platform to other businesses

**Context.** The owner wants to eventually lease/sell the platform to other
businesses running a similar model, while keeping them dependent on us and
protecting our source.

**Reality check (why "undecompilable code" is not the answer).** This is a web
app: the admin and customer frontends are JavaScript that must run in the
visitor's browser, so the browser necessarily receives readable (even if
minified/obfuscated) JS — it can always be inspected and copied. The backend is
Python bytecode, which bundlers (PyInstaller/Nuitka) and `.pyc` do not make
truly safe from reverse engineering. There is no way to ship a web app that
"cannot be decompiled". Obfuscation raises effort; it is deterrence, not
protection.

**The correct approach: multi-tenant SaaS (host it ourselves).** Do not ship the
code to clients at all. Run ONE codebase on OUR infrastructure and give each
client an isolated tenant (own subdomain/branding/login, own locations, plans,
bookings, users, data). The source never leaves our servers — nothing to
decompile — and billing/kill-switch control is the real "they depend on us"
lever: stop paying, we disable the tenant.

**Scope when pursued (its own future spec, sizeable).**
- Tenant model + per-tenant data isolation (tenant_id scoping on every table/
  query, or schema/db-per-tenant), enforced in the service layer, not just UI.
- Subdomain/host-based tenant resolution and routing.
- Tenant provisioning, branding, and a billing/subscription + suspend flow.
- Careful review of every existing query for tenant scoping; migration of the
  current single-tenant data into tenant 1.

**Weaker fallback (only if a client insists on self-hosting).** Ship with a
phone-home license key check + obfuscation. Explicitly deterrence, not true
protection; pair with a strong contract. Strictly worse than hosting ourselves.

**Status:** deferred by owner decision (recorded 2026) — "keep single-tenant for
now; revisit later." Deploy the owner's own single business first. Not scheduled.

## Deployment / data-migration follow-ups (staging trial, Nov 2026)

Items surfaced during the first VPS deploy + MariaDB→Postgres migration. None
block the staging trial; all must be handled before/at production cutover.

1. **Catalog images not migrated.** `upload_images.py` was skipped, so plan/
   cake/decor `object_key`s still point at legacy image references, not R2 — so
   catalog images render blank. Before cutover: either run the image migration
   (upload old images to R2 + rewrite keys) or re-upload key images in admin.
2. **3 duplicate active bookings skipped** (old ids 2261, 2752, 3070). The old
   MariaDB allowed two active bookings on the same (location, slot, date); the
   new partial unique index does not, so these were skipped on load (validate.py
   reports the resulting count + ₹4,500 payments-sum difference — fully
   accounted for). Resolve these in the old system (cancel/reject the extras)
   before the production cutover migration so nothing is silently dropped.
3. **Migrated users have random passwords + must_reset_password=true.** Legacy
   plain-text passwords were intentionally NOT copied. Staff cannot log in until
   their passwords are reset (or accounts recreated). Provide a reset path or
   create fresh admin/staff accounts before go-live. (The `owner` admin used in
   staging was seeded separately.)
4. **`seed_min` crashes when catalog already exists.** `_ensure_min_catalog`
   uses `scalar_one_or_none()` to check for an existing plan; with migrated data
   (many plans at a location) it raises `MultipleResultsFound`. Harmless (admin
   is created first), but fix the check (use `.first()`/limit) so the job is
   safe to re-run against populated DBs.
5. **Rotate secrets before production.** DB password, JWT secret, R2 access/
   secret keys, and the `owner` admin password were generated/entered during the
   staging session and shared in plaintext over chat. Generate fresh values at
   cutover and never reuse the staging ones for production.

## Safari / iOS cross-site cookie auth (fix at domain cutover)

**Symptoms (staging, Apple devices only).** On iPhone/Mac Safari the admin panel
logs out on refresh, and authenticated booking fetches fail ("booking loading
failed"). Chrome/Android are unaffected.

**Root cause.** During the staging trial the admin panel is on
`cineceleb-admin.pages.dev` and the API is on `142.93.208.192.sslip.io` — two
DIFFERENT registrable domains. The httpOnly auth cookie is therefore a
third-party/cross-site cookie (`SameSite=None; Secure`). Safari's Intelligent
Tracking Prevention blocks third-party cookies by default, so the cookie is not
persisted/sent — every reload and every authenticated XHR is unauthenticated.

**Why there's no small code fix.** No cookie flag makes a third-party cookie
survive Safari ITP. `SameSite=None; Secure` is already correct for cross-site; the
browser still drops it.

**Proper fix (at production cutover).** Serve the admin and the API on the SAME
registrable domain as subdomains, e.g. `admin.cinematiccelebration.in` +
`api.cinematiccelebration.in`. The cookie then becomes same-site (set
`COOKIE_SAMESITE=lax`, `COOKIE_SECURE=true`) and Safari keeps it. This is already
part of the planned domain cutover — no app code change needed, just DNS + the
Pages/Caddy host config and the `.env` cookie/CORS values.

**Interim.** Known staging limitation; staff use Chrome/Android during the trial.

**Alternative (only if Safari must work pre-cutover).** Add an Authorization:
Bearer token path (JWT held in memory, refreshed on load) so auth doesn't depend
on a third-party cookie. This is a real auth change (login response, admin client,
and the `get_current_user` dependency) and should get its own small spec + tests.
Not needed if the cutover is near.

## LED number pricing (FIXED, Nov 2026)

The LED charge counted only letters (A–Z), so digits in an LED name (e.g. "23",
"ARUN 30") were not charged. Fixed in `services/pricing.py`: `led_letter_count`
now counts ASCII letters AND digits (spaces/punctuation still ignored). Tests
updated (`test_pricing_examples.py`, `test_pricing_extended.py`). The draft
`led-number-pricing` spec stub is superseded by this fix and can be removed.

## Kids count on operational sheets + confirmation email (deferred)

**Context.** customer-booking-flow-v2 added a per-booking `kids` count (3–10 yrs)
alongside `people` (adults). The customer flow, admin booking form/list/summary,
and the public status page now all surface adults + kids. The **operational
sheets** (time sheet, cake sheet) and the **booking-confirmation email** still
show only "People" (adults); they predate v2 and were never specced to include
kids.

**Concern.** On-floor staff reading the printed time/cake sheet see the adult
count, not total headcount (adults + kids). For catering/seating the total
matters.

**Why it's deferred.** It's a cross-layer change for a display-only nicety (no
money or booking-integrity impact — pricing already accounts for kids
server-side). Touching it means:
- `apps/api/app/schemas/sheets.py` — add `kids` to `TimesheetRow` (and
  `CakesheetRow` if useful).
- `apps/api/app/services/sheets.py` — populate `kids` from the booking.
- `apps/api/app/services/excel.py` — add a "Kids" column (or change "People" to
  show `people + kids` / "N (+M kids)") in `build_timesheet_xlsx`.
- `apps/admin/src/features/timesheet/` — `types.ts` (`TimesheetRow.kids`) and
  `TimesheetPage.tsx` (render it).
- `apps/api/app/services/email.py` — add kids to the confirmation email body.
- Update `test_timesheet.py` / sheet tests.

**Proposed display.** Show total guests with a kids breakdown, e.g. "6 (+2
kids)", rather than a separate column, to keep the printed sheet compact. Keep
"People" meaning adults in any machine-read column.

**Status:** deferred (recorded 2026). Not scheduled. Pricing and all booking
screens already handle kids; this is sheets/email presentation only.


## Cake categories (Standard / Premium) with tabbed customer picker (deferred)

**Context.** The customer "Add a cake" step shows cakes as image cards. The
owner wants cakes grouped into two categories — **Standard** and **Premium** —
shown as two tabs, mirroring the special-decor category pattern.

**Why deferred.** Unlike decor (whose category already exists), `cakes` has no
category column, so this needs a backend change, not just UI:
- Migration `cakes.category` TEXT NOT NULL DEFAULT 'standard', CHECK
  `category IN ('standard','premium')`; backfill existing rows to 'standard'.
- `Cake` model + `CakeRead` (public) + admin cake create/edit schemas/forms gain
  `category`; admin decor-style select.
- Web `Cake` type gains `category`; the Cake step renders two tabs and filters
  cards by the active tab.
- Tests for the new field + the tabbed picker.

**Status:** deferred (recorded 2026). The cake image cards + weight popup ship
now; only the Standard/Premium tabbing is deferred.

## "Allow multiple" flag for special decor (deferred)

**Context.** ~90% of special-decor items are only ever ordered as quantity 1;
only a few (party popper, sash) are occasionally multiples. The customer decor
card currently shows an inline quantity stepper once an item is selected.

**Idea.** Add a per-item `allow_multiple` boolean on `special_decor_items`
(admin-set). When false, the customer card is a plain select (qty fixed at 1, no
stepper); when true, the inline stepper appears. Keeps the UI clean for the
common case and only exposes quantity where it's actually used.

**Why deferred.** Needs a backend field:
- Migration `special_decor_items.allow_multiple` BOOLEAN NOT NULL DEFAULT false.
- Model + public `SpecialDecorRead` + admin decor create/edit schemas/forms.
- Web `SpecialDecor` type + `DecorByCategory` conditionally renders the stepper.

**Interim (shipping now).** Every selected decor item shows a small inline
`- 1 +` stepper; unselected items show none. Good enough until the flag lands.

**Status:** deferred (recorded 2026). Not scheduled.
