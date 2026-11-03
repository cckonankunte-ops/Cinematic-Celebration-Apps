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
