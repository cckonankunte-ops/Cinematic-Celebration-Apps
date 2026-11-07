# Requirements — Admin Booking Search & Filter

## Introduction

With real data migrated, the admin bookings list now holds 3000+ bookings, so
staff need to search and filter rather than scroll. This feature adds, to the
admin bookings page: a text search with a "search in" field selector, a status
filter, and a smart date-range filter. All filtering is **server-side** and
**paginated** (the list is too large to filter in the browser), and remains
**location-scoped** (staff see only their assigned location; admins see the
selected location).

This extends the existing `GET /api/v1/admin/bookings` endpoint and
`services/booking.list_bookings` — it does not create a new endpoint or bypass
the existing access checks.

### Steering-derived constraints

- Location/role access is enforced in the service layer (`assert_location_access`),
  not just the UI. Staff cannot search outside their location.
- Request params are Pydantic/validated query params; no raw dicts.
- Search must be server-side SQL (Postgres), paginated; never fetch-all-then-filter.
- No new heavy dependency; use existing SQLAlchemy query building.
- PII (names/phones) stays within the authenticated, location-scoped response.

## Requirements

### Requirement 1: Text search with a field selector

**User Story:** As admin/staff, I want to search bookings by a chosen field, so
that I can quickly find a specific booking.

#### Acceptance Criteria

1. THE bookings API SHALL accept an optional search query string `q` and a
   search field `search_in` with allowed values: `any`, `customer_name`,
   `phone`, `booking_ref`, `occasion_person`, `name_on_cake`.
2. WHEN `search_in = customer_name` THE system SHALL match `q` as a
   case-insensitive substring of the booking's customer name.
3. WHEN `search_in = phone` THE system SHALL match `q` against the phone as a
   **digits-only substring**: both the stored phone and `q` are reduced to digits
   (spaces, `+`, and a leading `91` country code ignored), then matched as
   "contains". A partial query of any length (3, 4, 5+ digits) matches any phone
   containing that digit sequence (short queries naturally match many rows; staff
   type more digits to narrow).
4. WHEN `search_in = booking_ref` THE system SHALL match `q` as a
   case-insensitive substring of the booking reference.
5. WHEN `search_in = occasion_person` THE system SHALL match `q` against the
   special-person name (case-insensitive substring).
6. WHEN `search_in = name_on_cake` THE system SHALL match `q` against the
   name-on-cake field (case-insensitive substring).
7. WHEN `search_in = any` (default) THE system SHALL match `q` across customer
   name, phone, booking reference, special-person name, and name-on-cake.
8. WHEN `q` is empty/absent THE system SHALL apply no text filter.

### Requirement 2: Smart date-range filter

**User Story:** As admin/staff, I want flexible date filtering, so that I can
view all bookings, a single day, or a span.

#### Acceptance Criteria

1. THE bookings API SHALL accept optional `date_from` and `date_to` (plain dates,
   Asia/Kolkata booking dates).
2. WHEN neither date is provided THE system SHALL NOT filter by date (all dates).
3. WHEN only one date is provided THE system SHALL return bookings for exactly
   that day.
4. WHEN both dates are provided THE system SHALL return bookings with
   `booking_date` between them inclusive.
5. IF `date_from` is after `date_to` THE system SHALL treat them as swapped (or
   reject with 422) — never silently return nothing misleadingly.
6. THE existing single `date` param SHALL remain supported for backward
   compatibility (equivalent to `date_from = date_to = date`).

### Requirement 3: Status filter

**User Story:** As staff, I want to filter by status, so that I can act on
pending bookings or review a status.

#### Acceptance Criteria

1. THE bookings API SHALL accept an optional `status` with allowed values
   `pending`, `accepted`, `rejected`, `expired`.
2. WHEN a status is given THE system SHALL return only bookings in that status.
3. WHEN no status is given THE system SHALL exclude `rejected` by default
   (preserving current behaviour).

### Requirement 4: Server-side pagination

**User Story:** As the system, I must paginate so a 3000+ row list stays fast
and the 1 GB VPS is never asked to load the whole table at once.

#### Acceptance Criteria

1. THE bookings API SHALL accept `limit` with allowed page sizes **50, 100, 200**
   (default 50) and `offset` (default 0). There is NO "all / unlimited" option;
   `limit` is hard-capped at 200 server-side to protect memory as data grows.
2. THE response SHALL return the page of matching bookings plus a total match
   count so the UI can show "showing X of N" and drive next/prev.
3. THE query SHALL be executed in the database (SQL `LIMIT/OFFSET` + `COUNT`),
   never by loading all rows into the app.
4. Results SHALL keep a stable, sensible order (booking_date desc, then
   start_time, then id) so pagination is consistent.
5. ALL matching bookings remain reachable via pagination (next/prev or
   load-more); the filters (search/date/status) are the intended way to narrow
   large result sets.

### Requirement 5: Location & role scoping preserved

**User Story:** As the business, staff must only search their own location.

#### Acceptance Criteria

1. THE search SHALL enforce `assert_location_access(actor, location_id)` exactly
   as the current list does.
2. A staff user SHALL NOT be able to retrieve bookings outside their assigned
   location via any search/date/status/pagination parameter.

### Requirement 6a: Search interaction (debounced live + Enter)

**User Story:** As staff, I want responsive type-as-you-go search without
hammering the server.

#### Acceptance Criteria

1. THE text search SHALL be live/debounced: it fires ~350ms after the user stops
   typing, and immediately on Enter.
2. THE live search SHALL only fire when the text query has **at least 3
   characters**; with fewer than 3 characters no text filter is applied (the list
   shows the current date/status-scoped results).
3. THE "search in" dropdown, status dropdown, and date inputs SHALL apply
   immediately on change (they are discrete selections, not keystrokes).
4. Clearing the text box SHALL remove the text filter and refresh.

### Requirement 6: Admin UI

**User Story:** As admin/staff, I want controls on the bookings page for all of
the above.

#### Acceptance Criteria

1. THE bookings page SHALL show a text input + a "search in" dropdown (the six
   options from R1), a status dropdown (All + four statuses), and two date
   inputs (from / to).
2. WHEN the user changes any control THE list SHALL refresh via the API with the
   combined filters (debounced for the text input).
3. THE page SHALL show the total match count, a page-size selector (50 / 100 /
   200), and pagination (next/prev or load-more) driven by the API.
4. Empty dates SHALL mean "all dates"; one date = that day; two = range — matching R2.
5. THE page SHALL remain usable on mobile (staff use phones).

## Mandatory test cases

Because this touches access control and a PII-bearing query:

1. Text search per field (`customer_name`, `phone`, `booking_ref`,
   `occasion_person`, `name_on_cake`, `any`) returns the right matches.
2. Date logic: none = all; one = that day; two = inclusive range; reversed dates
   handled.
3. Status filter returns only that status; default excludes rejected.
4. Pagination: limit/offset returns the correct page + correct total count.
5. **Access control:** a staff user cannot retrieve another location's bookings
   via the search endpoint regardless of params.
