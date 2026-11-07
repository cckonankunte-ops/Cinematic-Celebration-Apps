# Design — Admin Booking Search & Filter

## Overview

Extend the existing `GET /api/v1/admin/bookings` endpoint and
`services/booking.list_bookings` with text search, status, a smart date range,
and server-side pagination (with a total count). Location/role scoping is reused
unchanged. The admin bookings page gains search/filter controls and pagination.

No new endpoint; additive params only, so existing callers keep working.

## API changes

### Endpoint params (`routers/admin/bookings.py`, `list_bookings`)

Add optional query params (all validated):
- `q: str | None` — text query.
- `search_in: Literal["any","customer_name","phone","booking_ref","occasion_person","name_on_cake"] = "any"`.
- `date_from: date | None`, `date_to: date | None` (keep existing `date` alias).
- `status: str | None` (existing).
- `limit: int = 50` (allowed 50/100/200; clamped to [1,200] server-side),
  `offset: int = 0` (>=0).

### Response

Change the response to include the total count for pagination. New schema:
```python
class BookingListPage(BaseModel):
    items: list[BookingListItem]
    total: int
    limit: int
    offset: int
```
The router returns `BookingListPage`. (The admin client is updated to read
`.items`/`.total`.)

## Service changes (`services/booking.list_bookings`)

Signature gains: `q`, `search_in`, `date_from`, `date_to`, `limit`, `offset`;
returns `(items, total)`.

Query building (SQLAlchemy, all in SQL):
1. Base: `select(Booking).outerjoin(Slot)` + `assert_location_access` +
   `Booking.location_id == location_id` (unchanged).
2. Date:
   - `date` (legacy) → `date_from = date_to = date` if the new params unset.
   - none → no date filter; one → equality; both → `between` (swap if reversed).
3. Status: given → equality; else exclude `rejected` (unchanged default).
4. Text (when `q` has >=3 chars after strip):
   - `customer_name`: `Booking.booking_name ILIKE %q%`.
   - `booking_ref`: `Booking.booking_reference ILIKE %q%`.
   - `occasion_person`: `Booking.special_person_name ILIKE %q%`.
   - `name_on_cake`: `Booking.name_on_cake ILIKE %q%`.
   - `phone`: digits-only contains — compare
     `regexp_replace(Booking.phone, '\D', '', 'g') LIKE %<digits(q) stripped of leading 91>%`.
   - `any`: OR of all the above.
5. Count: `select(func.count()).select_from(subquery)` with the same filters
   (before limit/offset).
6. Page: `.order_by(Booking.booking_date.desc(), Booking.start_time, Booking.id)
   .limit(limit).offset(offset)`.

Return `(rows, total)`. A thin phone-digits helper strips non-digits and a
leading `91`.

## Admin UI (`apps/admin/src/features/bookings/`)

- A filter bar above the list: text input + "search in" `<select>` + status
  `<select>` (All + 4) + two date inputs (from/to) + page-size `<select>`
  (50/100/200).
- A `useBookings` query keyed on all filter params; text input debounced 350ms,
  min 3 chars, Enter forces immediate; dropdowns/dates fire on change.
- Show "Showing X–Y of N" + Prev/Next (offset += limit). Reset offset to 0 when
  any filter changes.
- Mobile-friendly: controls wrap; the existing list/cards unchanged below.

## Testing

Backend (pytest, real Postgres):
1. Each `search_in` field returns correct matches; `any` matches across fields.
2. Phone digits-only partial match (3+ digits; ignores spaces/+91).
3. Date logic: none=all, one=that day, both=inclusive range, reversed handled.
4. Status filter; default excludes rejected.
5. Pagination: limit/offset page correctness + `total` correct; limit clamped to 200.
6. Access control: staff cannot read another location's bookings via any param.

Frontend (vitest): filter bar renders; debounce + min-3-char gate; pagination
controls update offset; page-size change refetches.
