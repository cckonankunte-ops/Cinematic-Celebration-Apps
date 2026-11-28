# Tasks: Payment history and payment channels

Branch: `feat/payment-history`. Each group ends with `ruff`, `pytest`, `eslint`
and `vitest` clean. Tests T1 to T24 are in `requirements.md`.

- [ ] 1. Database
  - [ ] 1.1 Migration `0027_add_payment_channel`: `payments.channel`,
        `ck_payments_channel`, `ck_payments_cash_consistent`,
        `ix_payments_received_at`, the two backfill statements, downgrade
  - [ ] 1.2 Update `models/payment.py` (`channel`, `PAYMENT_CHANNELS`,
        `MANUAL_PAYMENT_CHANNELS`, constraints and index)
  - [ ] 1.3 Update `tests/integration/test_schema_integrity.py` if it lists the
        payment constraints
  - [ ] 1.4 Tests: T18, T19 (upgrade, downgrade, upgrade on real Postgres)

- [ ] 2. Recording payments with a channel
  - [ ] 2.1 `PaymentCreate.channel` (required, manual channels only, cash pairing
        validator); `PaymentRead.channel`
  - [ ] 2.2 `record_payment` stores the channel and includes it in the event
  - [ ] 2.3 `AdminBookingCreate.advance_channel` (required with an advance,
        method derived from the channel when omitted); `create_admin_booking`
        stores it and logs it
  - [ ] 2.4 `void_payment` copies the channel onto the reversal
  - [ ] 2.5 Update the existing payment, void, ledger and booking-creation tests
        for the new required field
  - [ ] 2.6 Tests: T1, T2, T3, T4, T5, T6

- [ ] 3. Payment history API
  - [ ] 3.1 Result schemas in `schemas/analytics.py`
  - [ ] 3.2 `payment_history()` in `services/analytics.py` (rows, voided flag via
        EXISTS, recorded-by label, whole-range summary, paging)
  - [ ] 3.3 `GET /analytics/payment-history` with channel, limit and offset
  - [ ] 3.4 `build_payment_history_xlsx` and `GET .../export` with the row cap
  - [ ] 3.5 Tests: T7 to T17, T20

- [ ] 4. Admin: recording with a channel
  - [ ] 4.1 `lib/payment-channels.ts` (labels, manual list, method presets)
  - [ ] 4.2 `paymentFormSchema` and create schema updates; `PaymentDialog` Channel
        select (default Shop QR, presets method)
  - [ ] 4.3 `BookingForm` advance Channel select; send `advance_channel` through
        `BookingFormPage` and `booking-queries`
  - [ ] 4.4 Show the channel in the booking's payment list
  - [ ] 4.5 Update the existing PaymentDialog, BookingForm and schema tests
  - [ ] 4.6 Tests: T21, T22

- [ ] 5. Admin: Payment history tab
  - [ ] 5.1 Regenerate `openapi.json` and `schema.ts`
  - [ ] 5.2 `queries.ts`: channel support in `buildAnalyticsQuery`,
        `usePaymentHistory` (infinite paging)
  - [ ] 5.3 `PaymentHistoryTable.tsx` (cards, table, mobile layout, badges,
        links, Load more)
  - [ ] 5.4 `AnalyticsPage.tsx`: fourth tab, channel chips, export path, hide the
        status chips for this tab
  - [ ] 5.5 Tests: T23, T24

- [ ] 6. Docs and release
  - [ ] 6.1 Short note in `docs/` on channels and how to read the tab
  - [ ] 6.2 Run everything in the Codespace; commit regenerated API files
  - [ ] 6.3 Deploy: database backup, build API, `alembic upgrade head`, restart,
        then merge for the admin build
  - [ ] 6.4 Tell staff: choose the channel when recording a payment; Shop QR is
        preselected
