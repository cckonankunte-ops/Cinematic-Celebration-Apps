# Implementation Plan — Admin Booking Search & Filter

- [ ] 1. Service: extend `list_bookings` with search/date-range/pagination
  - In `apps/api/app/services/booking.py`, add params `q`, `search_in`,
    `date_from`, `date_to`, `limit`, `offset`; keep `on`/`status`. Build filters
    in SQL (ILIKE for text fields; digits-only regexp for phone; `any` = OR).
    Return `(items, total)` with count computed before limit/offset. Order by
    `booking_date desc, start_time, id`. Clamp limit to [1,200].
  - _Requirements: 1, 2, 3, 4, 5_

- [ ] 2. Schema + router
  - Add `BookingListPage {items, total, limit, offset}` to `schemas/booking.py`.
  - Update `GET /admin/bookings` in `routers/admin/bookings.py` to accept the new
    query params (Pydantic-validated, `search_in` as Literal) and return
    `BookingListPage`.
  - _Requirements: 1, 2, 3, 4_

- [ ] 3. Backend tests
  - Integration tests for: each search field + `any`; phone 3+ digit partial;
    date none/one/both/reversed; status + default-excludes-rejected; pagination
    page + total + limit clamp; staff cross-location denied.
  - _Requirements: 1, 2, 3, 4, 5; all mandatory test cases_

- [ ] 4. Admin UI: filter bar + pagination
  - In `apps/admin/src/features/bookings/`, add the filter bar (text + search-in
    select + status select + date-from/to + page-size select) and wire a
    `useBookings` query on all params. Debounce text 350ms, min 3 chars, Enter =
    immediate; dropdowns/dates immediate; reset offset on filter change. Show
    "Showing X–Y of N" + Prev/Next. Read `.items`/`.total` from the new response.
  - _Requirements: 6, 6a_

- [ ] 5. Frontend test + API types
  - Update the admin API client/types for the `BookingListPage` response.
    Add/adjust a vitest for the filter bar (debounce/min-3, pagination).
  - _Requirements: 6, 6a_

- [ ] 6. Verify + deploy
  - `ruff` + `pytest` (API), `eslint` + `vitest` (admin) green. Commit/push.
    On VPS: `git pull`, rebuild+restart api; admin auto-redeploys via Pages.
    Smoke-test search/date/status/pagination against the real 3000+ bookings.
  - _Requirements: all_
