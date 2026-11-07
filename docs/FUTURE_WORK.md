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
