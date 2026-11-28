# Tasks: Cashfree online payments

Branch: `feat/cashfree-payments`. Each task ends with `ruff`, `pytest`, `eslint`
and `vitest` clean. Tests listed in `requirements.md` (T1 to T32) are covered by
the tasks noted.

- [ ] 1. Prove the Cashfree details in sandbox (no app code depends on guesses)
  - [ ] 1.1 Owner: create sandbox App ID and Secret Key in the Cashfree
        dashboard and put them in the Codespace `.env` (never in chat or git)
  - [ ] 1.2 Add a throwaway script `scripts/cashfree_probe.py` that creates a
        sandbox order, prints the response keys, and verifies a pasted webhook
        signature with the Dev Studio sample. Confirm: pinned `x-api-version`,
        the Get Order and payments response shapes, webhook field names, and the
        signature formula. Record the findings at the top of `design.md`
  - [ ] 1.3 Delete the script once the findings are recorded

- [ ] 2. Configuration
  - [ ] 2.1 Add the settings in `core/config.py` with the validation in R9.2
  - [ ] 2.2 Update `.env.example` with every new variable (no real values)
  - [ ] 2.3 Tests: T29

- [ ] 3. Database migration `0027_add_cashfree_payments`
  - [ ] 3.1 `bookings.payment_channel`, `bookings.hold_expires_at`
  - [ ] 3.2 `payment_orders` and `payment_webhook_events` with named constraints
  - [ ] 3.3 `uq_payments_provider_ref` partial unique index
  - [ ] 3.4 Extend `ck_booking_events_type` with `payment_failed` and
        `payment_needs_refund`
  - [ ] 3.5 Models and downgrade; update `tests/integration/test_schema_integrity.py`
  - [ ] 3.6 Run upgrade, downgrade, upgrade against real Postgres

- [ ] 4. Provider interface and Manual provider
  - [ ] 4.1 New dataclasses and Protocol in `integrations/payments/base.py`
  - [ ] 4.2 Adapt `ManualProvider` (instructions text moves into `OrderResult`)
  - [ ] 4.3 `get_payment_provider()` reads `PAYMENT_PROVIDER`
  - [ ] 4.4 Add `GatewayUnavailableError` and `GatewayRejectedError`
  - [ ] 4.5 Tests: T26 (manual path unchanged)

- [ ] 5. Cashfree provider (`integrations/payments/cashfree.py`)
  - [ ] 5.1 Promote `httpx==0.28.1` to a runtime dependency (one-line reason in
        the PR: already pinned for tests, avoids hand-rolled HTTP)
  - [ ] 5.2 `create_order` with exact Decimal amount, expiry, return and notify
        URLs, short timeouts, no retries
  - [ ] 5.3 `get_order` (order + payments) mapped to our enums
  - [ ] 5.4 `verify_webhook`: HMAC check, parse, event keys
  - [ ] 5.5 Tests with `httpx.MockTransport`: T4, T7, T13 (provider side)

- [ ] 6. Gateway service (`services/payment_gateway.py`)
  - [ ] 6.1 `online_advance_paise` (rule, floor ₹500, cap at total). Tests: T3
  - [ ] 6.2 `start_checkout` and order attempts. Tests: T15 (retry)
  - [ ] 6.3 `confirm_paid` as one transaction with row lock and idempotency.
        Tests: T6, T8, T9, T14, T16
  - [ ] 6.4 Late and inactive booking handling. Tests: T23, T24
  - [ ] 6.5 `handle_webhook` (verify, de-duplicate, confirm via Get Order,
        ordering rules, amount mismatch). Tests: T7, T10, T11, T12, T13
  - [ ] 6.6 `reconcile_booking` and `reconcile_before_expiry`. Tests: T17 to T22

- [ ] 7. Wire into customer booking creation
  - [ ] 7.1 `create_customer_booking`: set channel, `hold_expires_at`, online
        amount in `advance_paise`; after commit call the gateway, fall back to
        manual on `GatewayUnavailableError`. Tests: T1, T2, T5, T25
  - [ ] 7.2 Extend `CustomerBookingResult` and `PublicBookingStatus`
  - [ ] 7.3 `POST /public/bookings/{token}/pay` with rate limit. Tests: T15, T28

- [ ] 8. Webhook endpoint
  - [ ] 8.1 `routers/webhooks/cashfree.py`, size cap, status codes per design
  - [ ] 8.2 Register in `main.py`; confirm no origin or role dependency applies
  - [ ] 8.3 Tests: T7, T8, T12, T28, T30 (end to end through TestClient)

- [ ] 9. Expiry job
  - [ ] 9.1 Manual pass unchanged; add the gateway pass with reconcile
  - [ ] 9.2 Tests: T17 to T22; existing `test_expire.py` still passes

- [ ] 10. Admin changes
  - [ ] 10.1 Expose `payment_channel` and `needs_refund` in admin booking schemas
  - [ ] 10.2 Booking list/edit label, "payment received on inactive booking"
        banner, Cashfree rows in payment history
  - [ ] 10.3 Regenerate `openapi.json` and `schema.ts`
  - [ ] 10.4 vitest for the banner and labels

- [ ] 11. Customer site
  - [ ] 11.1 `lib/api.ts` types and `payBooking`
  - [ ] 11.2 `lib/cashfree.ts` (lazy SDK load, redirect checkout)
  - [ ] 11.3 `BookingWizard.tsx` post-submit flow for gateway and manual
  - [ ] 11.4 `BookingStatus.tsx` states, polling, countdown, retry button
  - [ ] 11.5 Privacy policy line
  - [ ] 11.6 vitest: T31, T32; check the booking page bundle is still under
        150 KB gzipped

- [ ] 12. Docs and runbook
  - [ ] 12.1 `docs/OPS_RUNBOOK.md`: dashboard setup (keys, webhook URL, domain
        whitelist, Transaction Time Limit), going live, rollback to manual, how
        to refund by hand and void the ledger entry, what to do when a payment
        arrives on an inactive booking
  - [ ] 12.2 Update `docs/` architecture notes

- [ ] 13. Sandbox end-to-end (owner + agent, in the Codespace, not the live VPS)
  - [ ] 13.1 Run the API and the customer site in the Codespace; forward the API
        port with public visibility; register
        `https://<codespace-url>/api/v1/webhooks/cashfree` in the **sandbox**
        dashboard; whitelist the Codespace site domain for sandbox checkout
  - [ ] 13.2 Walk through: success, failure then retry, abandon and expiry,
        duplicate webhook (dashboard resend), gateway down fallback
  - [ ] 13.3 Fix whatever the sandbox shows; update the design notes

- [ ] 14. Go live
  - [ ] 14.1 Owner: production keys into the server `.env`; whitelist
        `cinematiccelebration.in` and `www`; register the production webhook
  - [ ] 14.2 Switch `CASHFREE_ENV=production`, `PAYMENT_PROVIDER=cashfree`
  - [ ] 14.3 One small real payment, confirm auto-accept, refund it by hand in
        the dashboard, void the ledger entry
  - [ ] 14.4 Watch the first few days; rollback is `PAYMENT_PROVIDER=manual`
