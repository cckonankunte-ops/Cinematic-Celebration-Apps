# Design: Payment history and payment channels

Implements `requirements.md`. Follows `tech.md` and `structure.md`: routers thin,
rules in services, money in integer paise, the OpenAPI schema is the contract.

## 1. Overview

```
Record payment dialog / advance at booking creation
        |  channel (required, default Shop QR)
        v
routers/admin/payments.py, bookings.py -> services/payments.py, booking.py
        |  stores payments.channel, copies it onto void reversals
        v
payments table  (+ channel column, CHECKs, received_at index)

Analytics > Payment history tab
        |  GET /api/v1/admin/analytics/payment-history  (admin only)
        v
services/analytics.py: payment_history()  -> rows + whole-range summary
        |  GET .../payment-history/export -> services/excel.py
```

No new service, container, or dependency.

## 2. Data model (migration `0027_add_payment_channel`)

### `payments` changes
| change | detail |
|---|---|
| new column `channel` | text, NULL allowed |
| `ck_payments_channel` | `channel IS NULL OR channel IN ('cash','shop_qr','pos','advance_qr','cashfree','other')` |
| `ck_payments_cash_consistent` | `(method <> 'cash' OR channel IS NULL OR channel = 'cash') AND (channel IS DISTINCT FROM 'cash' OR method = 'cash')` |
| `ix_payments_received_at` | index on `received_at`, for date-range reads |

Backfill in the same migration (data only, no amounts or dates touched):
1. `UPDATE payments SET channel='cash' WHERE method='cash' AND reverses_payment_id IS NULL`
2. `UPDATE payments r SET channel = o.channel FROM payments o WHERE r.reverses_payment_id = o.id AND r.channel IS NULL` (reversals copy the original; for cash originals this gives `cash`)

All other rows keep `channel = NULL` ("Not specified"). Downgrade drops the two
constraints, the index and the column. Constraint names are explicit, as required.

`models/payment.py`: add `channel`, `PAYMENT_CHANNELS` (all six) and
`MANUAL_PAYMENT_CHANNELS` (all except `cashfree`), plus the new constraints in
`__table_args__`.

## 3. Backend

### 3.1 Schemas (`schemas/payment.py`, `schemas/booking.py`)
- `PaymentCreate`: new required `channel: Literal["cash","shop_qr","pos","advance_qr","other"]`.
  A model validator enforces the cash pairing (R1.4); a mismatch returns `422`
  with a clear message. `cashfree` is not in the Literal, so it is rejected.
- `PaymentRead`: new `channel: str | None`.
- `AdminBookingCreate`: new `advance_channel` (same Literal, optional). A model
  validator requires it when `advance_amount_paise` is set. When
  `advance_method` is omitted the server derives the method from the channel
  (cash to cash, shop_qr and advance_qr to upi, pos to card, other to other),
  then applies the cash pairing check.
- The public booking schemas are untouched.

### 3.2 Services
- `services/payments.record_payment`: save `channel`; add it to the
  `payment_recorded` event value.
- `services/booking.create_admin_booking` (advance block): save `advance_channel`
  as the payment's channel; add it to the `payment_recorded` event.
- `services/payments.void_payment`: the reversal copies `channel` from the
  original.
- Today income, ledger and derived-amount functions are unchanged.

### 3.3 Payment history query (`services/analytics.py`)
```python
def payment_history(db, actor, *, location_id, date_from, date_to,
                    channels: Sequence[str], limit: int, offset: int)
        -> PaymentHistoryResult
```
- `assert_location_access`, `validate_range`, IST bounds from the existing
  `_ist_bounds` (half-open `[start, end)`).
- Base filter: `Payment` joined to `Booking` on `booking_id`, `Booking.location_id
  == location_id`, `Payment.received_at` in range, and the channel filter. The
  special filter value `unspecified` matches `channel IS NULL`.
- Rows: select `Payment`, `Booking.booking_reference`, `Booking.booking_name`,
  and `User.username` through an outer join on `recorded_by_user_id`; order by
  `Payment.received_at, Payment.id`; `limit`/`offset`.
- `is_reversal` = `reverses_payment_id IS NOT NULL`. `is_voided` = an `EXISTS`
  on another payment whose `reverses_payment_id` equals this id (evaluated in
  the database, so it is correct even if the reversal is outside the range).
- `recorded_by`: username; else provider title (for example "Cashfree"); else
  "Migrated" when the note is `migrated`; else "Unknown user".
- Summary (separate aggregate over the same base filter, ignoring limit/offset):
  `total_paise` (sum of `amount_paise`), `payment_count`, and `by_channel`
  (`COALESCE(channel, 'unspecified')` to paise).
- `total_rows` from `COUNT(*)`; `has_more = offset + len(rows) < total_rows`.
- No phone or email is selected.

Result schemas in `schemas/analytics.py`:
```python
class PaymentHistoryRow(BaseModel):
    id: int; received_at: datetime; booking_id: int
    booking_reference: str; booking_name: str
    channel: str | None; method: str; amount_paise: int
    recorded_by: str; provider_ref: str | None; note: str | None
    is_reversal: bool; is_voided: bool

class PaymentHistorySummary(BaseModel):
    total_paise: int; payment_count: int; by_channel: dict[str, int]

class PaymentHistoryResult(BaseModel):
    rows: list[PaymentHistoryRow]; summary: PaymentHistorySummary
    total_rows: int; limit: int; offset: int; has_more: bool
```

### 3.4 Router (`routers/admin/analytics.py`)
- `GET /api/v1/admin/analytics/payment-history`: query params `location_id`,
  `date_from`, `date_to` (existing `_date_range` helper), repeatable `channel`,
  `limit` (default 200, maximum 500), `offset`. Admin only like the rest of the
  router (`require_role("admin")`, `check_origin`).
- `GET .../payment-history/export`: same filters, no pagination, capped at
  20,000 rows (more returns `422` asking to narrow the range). Streams the xlsx.
- Invalid channel values return `422`.

### 3.5 Excel (`services/excel.py`)
`build_payment_history_xlsx(result)`: sheet "Payments"; columns Date and time
(IST), Booking reference, Customer, Channel, Method, Amount (Rs.), Recorded by,
Reference, Note, Status (Voided / Reversal / blank). Footer: total received and
one total per channel. Reuses the existing helpers and number formats.

## 4. Admin app

- `lib/payment-channels.ts` (shared by bookings and analytics): the channel list
  with labels, the manual-channel list, the channel-to-method preset map, and a
  `channelLabel()` that returns "Not specified" for empty.
- `features/bookings/booking-schema.ts`: `paymentFormSchema` gains `channel`
  (enum of manual channels, required); the create schema gains `advance_channel`
  (default `shop_qr`).
- `PaymentDialog.tsx`: Channel select above Method, default Shop QR; changing it
  presets Method via `setValue('method', ...)`; sends `channel`.
- `BookingForm.tsx` advance fieldset: a Channel select (default Shop QR) with the
  same preset; `BookingFormPage.tsx` / `booking-queries.ts` send
  `advance_channel`.
- `PaymentHistory.tsx` (booking screen): show the channel label on each row.
- `types.ts`: `PaymentChannel`, `PaymentRead.channel`.
- Analytics:
  - `AnalyticsPage.tsx`: new tab `payments` ("Payment history", export path
    `/api/v1/admin/analytics/payment-history/export`); a channel chip group shown
    for this tab (the booking status chips are hidden for it); From/To default
    to today.
  - `queries.ts`: `buildAnalyticsQuery` accepts channels; `usePaymentHistory`
    uses TanStack `useInfiniteQuery` (offset paging, "Load more").
  - `PaymentHistoryTable.tsx` (new): summary cards (Total received, Payments, one
    per channel), table with the columns in R3.4, "Voided" and "Reversal"
    badges, negative amounts in red, booking reference as a link to
    `/bookings/:id/edit`, a "Showing N of M" line and a Load more button. On a
    phone the rows collapse to cards.
  - Date and time uses the existing `formatDateTime` (IST).
- Types come from `openapi-typescript` (`npm run gen:api`) where used.

## 5. Failure modes and edge cases

| situation | behaviour |
|---|---|
| Old payment with no channel | shown as "Not specified", filterable via a "Not specified" chip |
| Void on a later day than the original | the reversal row appears on the day it was made, the original keeps its own day and shows "Voided" |
| Manual payment with method cash and channel Shop QR | rejected `422` (R1.4) |
| Branch with thousands of rows | paged; summary still covers the whole range; export capped with a clear message |
| Admin of another role calls the API | `403` |
| Cashfree later writes `cashfree` | allowed only in the gateway code path, not by the manual API |

## 6. Rollout

Migration plus API plus admin build. Backward compatibility note: the Record
payment API now requires `channel`, so any script or client calling it must send
it (the admin app is updated in the same release; there are no other callers).
Deploy order is the usual: back up, build the API, run `alembic upgrade head`,
restart the API, then merge so Pages rebuilds the admin. Rollback: the
downgrade drops the column; older admin code keeps working only if the API
still accepts payments without a channel, so roll back both together.

## 7. Cost and memory

None. One extra indexed column and one index; queries are range reads over a
few tens of payments a day.
