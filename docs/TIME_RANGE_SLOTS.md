# Time-range slots — operations & retrofit notes

This feature replaces label-only slots with **time-range slots** (`start_time` +
`duration_minutes`), adds per-location working hours + a late-booking cutoff,
and prices by `(plan, duration)`. Spec: `.kiro/specs/time-range-slots/`.

## Configuration

- `CLEANING_BUFFER_MINUTES` (env, default `30`): the turnaround gap enforced
  **after** each booking. It is a **service-layer policy** applied to new
  bookings (the booking pre-check and public availability), NOT a database
  constraint. Changing it takes effect immediately — no migration needed.
- Working hours, the online cutoff, and the late-booking switch are **per
  location** (admin-editable under Catalog → “Location hours & online booking”).

## Rules (enforcement points)

| Rule | Where | Who it blocks |
|---|---|---|
| Overlap (same usable time, per location+plan+date) | DB exclusion constraint `excl_bookings_active_overlap` + service pre-check | everyone (physical) |
| Cleaning buffer gap | service pre-check + availability | new bookings only |
| Start on the hour/half-hour | Pydantic + DB CHECK | slot create |
| Within working hours | service + slot create | everyone |
| Usable end ≤ close | service | customer/staff (admin may override) |
| Start in the future | service | customer/staff (admin may book past) |
| Online cutoff (late start) | service + availability | public only (staff/admin exempt) |

Why the buffer is service-only: a retroactive buffer would invalidate legitimate
historical back-to-back bookings (e.g. an 8 PM handoff). The DB guarantees the
physical invariant (no overlapping *usable* time); the buffer is operational
policy for new bookings.

## Duration-based pricing

Base price + advance come from `plan_pricing` keyed by `(plan_id,
duration_minutes)`, resolved on the booking date; falls back to the plan's own
`price_paise`/`advance_paise` when no row exists. People allowance and the
extra-guest charge remain on the plan (they do not vary by duration). The
resolved price/advance are snapshotted onto each booking.

## Retrofit runbook (one-off, real Postgres)

Run in order; migration B (0012) enforces constraints only after the data is
clean.

```bash
# 1. Additive schema (nullable columns + plan_pricing + btree_gist)
cd apps/api && alembic upgrade 0011

# 2. Backfill: parse slot descriptions -> start/duration, snapshot bookings,
#    seed plan_pricing, and report overlaps. Unparseable rows are reported,
#    never guessed. (Run from repo root.)
export DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/cinematic'
python -m scripts.migrate_time_slots.backfill --report retrofit_report.txt

# 3. Review retrofit_report.txt. Resolve any unparseable slots (map by hand) and
#    any overlapping ACTIVE bookings before continuing. The overlap pre-check
#    uses usable-time (buffer=0) to match the DB constraint.

# 4. Enforce constraints (NOT NULL, CHECKs, exclusion constraint). Fails loudly
#    if residual overlaps exist.
cd apps/api && alembic upgrade head
```

## Regenerate API types

After the API is running with these changes, regenerate the admin's typed
client so `schema.ts` matches:

```bash
cd apps/admin && npm run gen:api
```
