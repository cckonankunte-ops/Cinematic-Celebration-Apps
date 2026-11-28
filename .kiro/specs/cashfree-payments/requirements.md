# Requirements: Cashfree online payments for the customer booking flow

## Introduction

Today a customer booking is a **request**: it is created `pending`, holds the
slot for `PENDING_HOLD_MINUTES` (120), and returns manual UPI instructions.
Staff verify the money by hand, record it in the `payments` ledger, then accept.

This spec adds **Cashfree Payment Gateway** (hosted web checkout) so a customer
pays the **advance online** and the booking is **accepted automatically** on
confirmed payment. Manual UPI stays as a fallback when the gateway is
unavailable. Admin-created bookings are unchanged.

Written from Cashfree's current official docs (create order, hosted checkout,
webhooks and signatures, order and payment lifecycle) and the decisions below.
Details that only the sandbox can confirm are marked **[verify in sandbox]** and
tracked as tasks.

### Decisions (confirmed by the owner)

1. The customer pays only the **advance** online, using the existing
   threshold-rule advance. If no rule applies, the advance is the plan's advance,
   with a **minimum of ₹500** (see R2).
2. The slot is **held while the payment is open**, and **released** if the
   payment fails or is abandoned. On success the booking goes **straight to
   `accepted`**, with no `pending` step after payment confirmation.
3. After a successful payment the booking is accepted **automatically**.
4. **Refunds are done by hand** in the Cashfree dashboard. No refund button or
   API call from our admin.
5. **Manual UPI is the fallback** if the gateway is down. A manual payment is
   **not** auto-confirmed: the booking stays `pending` and staff accept it after
   verifying the money, exactly as today. (Cashfree cannot see a plain UPI
   transfer made straight to our VPA, so there is no auto-confirmation for it.)
6. Build and test on **Cashfree sandbox first**, then switch to production keys.
7. The customer page needs **payment pending, failed and retry** states.
8. **Payment gateway is configured per branch**, as configuration only. Today all
   three branches use the same Cashfree account; later a branch can point to a
   different account or a different gateway by changing the config (no code
   change, no schema change). This keeps the settlement-bank-account decision
   open.
9. **Every order is tagged with the branch**, whether or not the branches share
   an account.
10. Hold time is **15 minutes to pay plus a 10-minute allowance** for a payment
    already in flight.

### Out of scope

- Refund automation, partial refunds, payment links, subscriptions, EMI.
- Collecting the full amount online (advance only, for now).
- Changing admin-created bookings or the admin "Record payment" flow.
- Saved cards, wallets of ours, or storing any card/UPI details (Cashfree
  hosted checkout collects them; they never touch our servers).

## Glossary

- **Payment account**: one named set of gateway credentials from configuration
  (for example `main`): provider (`cashfree` or `manual`), environment (sandbox
  or production), App ID and secret key. Several branches may share an account.
- **Gateway booking**: a customer booking whose advance is paid through a
  gateway payment account (`payment_mode = 'gateway'`).
- **Manual booking**: a customer booking handled by the manual UPI flow
  (`payment_mode = 'manual'`), the current behaviour.
- **Payment order**: our record of one Cashfree order (one payment attempt
  session) for a booking. A booking can have several (retries).
- **Hold**: the time a `pending` booking keeps its slot.
- **Grace**: extra time after the hold during which a payment already in flight
  may still succeed (Cashfree's Transaction Time Limit).

## Requirements

### R1: Choose the payment channel when a customer books

**User story:** As a customer, I want to pay my advance online when I book, so my
slot is confirmed immediately.

Acceptance criteria:
1. WHEN a customer submits a valid booking request AND the booking's branch
   resolves (R11) to a gateway payment account, THE system SHALL create the
   booking `pending` with `payment_mode='gateway'`, create an order with that
   account's gateway for the advance, and return what the page needs to open
   checkout.
2. WHEN the branch resolves to the built-in `manual` account, THE system SHALL
   behave exactly as today (`payment_mode='manual'`, manual UPI instructions,
   `PENDING_HOLD_MINUTES`).
3. IF Cashfree order creation fails (network error, timeout, 5xx, or auth
   error), THEN THE system SHALL keep the booking, set
   `payment_mode='manual'`, apply the normal manual hold, and return manual
   UPI instructions plus a flag telling the page the gateway was unavailable.
   The booking SHALL NOT be accepted automatically.
4. THE client SHALL send only IDs and quantities. Any client-sent amount or
   total SHALL be ignored. The amount charged is computed by the server.
5. THE `PUBLIC` booking request schema SHALL NOT gain any payment-amount field.

### R2: Advance amount

**User story:** As the owner, I want the online amount to follow our advance
rules, with a ₹500 floor.

Acceptance criteria:
1. THE online amount SHALL be the booking's advance, resolved by the existing
   rule `resolve_advance_paise` against the final total (highest matching
   threshold rule, else the plan's `advance_paise`).
2. IF that value is below `ONLINE_ADVANCE_MIN_PAISE` (default 50000, ₹500), THEN
   THE online amount SHALL be raised to the minimum.
3. THE online amount SHALL NOT exceed the booking total.
4. FOR a gateway booking THE system SHALL store the online amount in
   `bookings.advance_paise`, so the "advance met" check used elsewhere matches
   what was charged.
5. Money SHALL stay in integer paise. Conversion to Cashfree's rupee amount
   SHALL use exact decimal arithmetic, never floats, and produce two decimals
   (for example 50000 paise is "500.00").

### R3: Slot hold while payment is open

**User story:** As a customer, I want my slot kept while I pay, and freed if I
don't pay.

Acceptance criteria:
1. A gateway booking SHALL hold its slot (status `pending`) for
   `GATEWAY_HOLD_MINUTES` (default **15**), stored as `bookings.hold_expires_at`.
   The allowance for a payment already in flight is `GATEWAY_GRACE_MINUTES`
   (default **10**, matching Cashfree's minimum transaction time limit).
2. THE Cashfree order SHALL be created with an expiry equal to `hold_expires_at`.
3. THE expiry job SHALL NOT expire a gateway booking before
   `hold_expires_at + GATEWAY_GRACE_MINUTES`, and SHALL first reconcile the
   order's real status with Cashfree (R7).
4. WHEN a gateway booking is past hold + grace and Cashfree confirms no
   successful payment, THE job SHALL set it `expired`, which frees the slot, and
   write the audit event.
5. A payment attempt that fails or is dropped SHALL NOT release the slot
   immediately; the customer may retry until the hold ends (R6).
6. Manual bookings SHALL keep the existing `created_at + PENDING_HOLD_MINUTES`
   behaviour.
7. THE database SHALL remain the double-booking guard (the existing overlap
   exclusion constraint on `pending` and `accepted`). Two customers cannot hold
   or pay for the same slot.

### R4: Automatic acceptance on confirmed payment

**User story:** As a customer, once my payment succeeds my booking is confirmed
without waiting for staff.

Acceptance criteria:
1. WHEN a verified success is received for a gateway booking in `pending`, THE
   system SHALL in ONE transaction: record the payment in the ledger, set the
   booking `accepted`, write the audit events, and update the lead state.
2. THE accepted booking SHALL satisfy the existing advance rule (paid >= advance).
3. THE confirmation email SHALL be sent after the commit (as admin accept does).
4. THE `accepted` event SHALL record the actor as the system (null user) with
   the gateway as the source.
5. PROCESSING the same success twice SHALL change nothing the second time
   (idempotent, R5.5).
6. IF the booking is already `accepted`, THEN THE system SHALL still record the
   payment if it is new, and SHALL NOT change the status.

### R5: Webhooks (source of truth)

**User story:** As the platform, I need to learn about payments even if the
customer closes the browser.

Acceptance criteria:
1. THE system SHALL expose `POST /api/v1/webhooks/{provider}/{account}` (for
   example `/api/v1/webhooks/cashfree/main`), unauthenticated by user session,
   protected only by signature verification, and excluded from the admin router
   so admin origin checks do not apply. Each payment account has its own
   address, registered in that account's dashboard.
2. THE system SHALL verify `x-webhook-signature` using HMAC-SHA256 over the
   `x-webhook-timestamp` header plus the **raw request body**, base64-encoded,
   with **that account's** secret key, compared in constant time. A delivery
   signed with another account's key SHALL be rejected. **[verify in sandbox
   with the Dev Studio verification tool]**
3. IF the signature is missing or invalid, THEN THE system SHALL respond `401`,
   change no data, and log only that verification failed (no body, no secrets).
4. THE system SHALL handle at least the payment success, failed and user-dropped
   events, and ignore other event types with `200`.
5. THE system SHALL be idempotent: a delivery repeated for the same Cashfree
   payment SHALL NOT create a second ledger row. This SHALL be enforced by a
   unique index on `(provider, provider_ref)` in `payments` plus a processed-
   events table keyed on the event identity, not only by an in-memory check.
   (The `x-idempotency-key` header is not present on every webhook version, so
   it is used only when present.)
6. Events MAY arrive out of order or more than once. A later success SHALL win
   over an earlier failure for the same order; a failure arriving after a
   success SHALL be ignored.
7. BEFORE accepting a booking on a success event, THE system SHALL confirm the
   order status with Cashfree's server API (Get Order). IF that call cannot be
   completed, THEN THE system SHALL respond with a 5xx so Cashfree retries.
8. THE system SHALL compare the paid amount and currency to the order. IF they
   differ, THEN THE system SHALL record the amount actually received, and
   decide acceptance by the normal advance rule (R4.2), logging the mismatch.
9. FOR unknown order ids or already-final bookings THE system SHALL respond `200`
   so Cashfree stops retrying.
10. THE handler SHALL respond quickly; the confirmation email SHALL be sent in
    the background.

### R6: Customer page states and retry

**User story:** As a customer, I want to see whether my payment worked and retry
if it didn't.

Acceptance criteria:
1. THE booking status page SHALL show one of: **Payment pending** (with a "Pay
   now" button and the time left to pay), **Confirmed**, **Payment failed**
   (with "Try again" while the hold is active), **Expired** (slot released, start
   again), or **Awaiting manual confirmation** (manual channel).
2. WHEN the customer returns from checkout, THE page SHALL poll the status for up
   to about two minutes while the result is unknown, and SHALL NOT rely on the
   browser redirect alone to show "Confirmed".
3. WHEN the status endpoint is read for a gateway booking whose payment is still
   unresolved, THE server MAY reconcile with Cashfree (rate-limited, at most
   once every few seconds per booking) so a delayed webhook does not leave the
   customer waiting.
4. `POST /api/v1/public/bookings/{token}/pay` SHALL start a new payment
   attempt for a `pending` gateway booking within its hold, creating a new
   Cashfree order id (so an order is never reused after it failed), or resuming
   the active one. It SHALL be rate limited.
5. IF the booking is not `pending` or the hold has ended, THEN `/pay` SHALL
   refuse with a clear error and no order SHALL be created.
6. THE page SHALL show no payment details beyond amounts and status. THE public
   status response SHALL contain no personal data beyond what it shows today.
7. THE checkout SHALL open on Cashfree's hosted page (redirect, with a return
   URL back to the status page). The Cashfree SDK script SHALL load only when
   the customer starts payment, to keep the booking page bundle small.

### R7: Reconciliation and expiry

**User story:** As the owner, I don't want paid customers cancelled or unpaid
customers holding slots forever.

Acceptance criteria:
1. A payment CAN succeed after the order's expiry time (Cashfree honours an
   attempt started before expiry until its transaction time limit). THE
   system SHALL therefore reconcile before expiring.
2. THE expiry job SHALL, for each gateway booking past hold + grace, fetch the
   order and its payments from Cashfree. IF paid, THE job SHALL accept the
   booking (R4). IF a payment is still in flight, THE job SHALL skip it this
   run. IF the order is expired or terminal with no success, THE job SHALL
   expire the booking.
3. IF Cashfree cannot be reached, THEN THE job SHALL skip the booking and retry
   next run (never expire on an unknown).
4. THE job SHALL stay idempotent and run by cron, with no in-process scheduler.

### R8: Late payment on a booking that is no longer active

**User story:** As the owner, if money arrives for a booking whose slot was
already released, I need it handled safely and visibly.

Acceptance criteria:
1. WHEN a verified success arrives for a booking that is `expired`, THE system
   SHALL re-check the overlap. IF the slot is still free, THE system SHALL
   reinstate the booking as `accepted`, record the payment, and write the events.
2. IF the slot has been taken (or the booking is `rejected` or `cancelled`), THEN
   THE system SHALL record the payment in the ledger, leave the booking status
   unchanged, and write a `payment_needs_refund` audit event.
3. THE admin booking screen SHALL show a visible "Payment received on an
   inactive booking: refund via the Cashfree dashboard" banner whenever the
   booking is not active and its ledger paid total is above zero.
4. AFTER a manual refund in the Cashfree dashboard, THE admin SHALL record it by
   voiding the payment (existing admin-only void), which clears the banner.

### R9: Configuration and security

Acceptance criteria:
1. THE system SHALL read payment configuration from the environment (secrets
   never in the database or admin screens) and list every variable in
   `.env.example`: the payment accounts and branch mapping described in R11,
   plus `GATEWAY_HOLD_MINUTES`, `GATEWAY_GRACE_MINUTES`,
   `ONLINE_ADVANCE_MIN_PAISE` and `PUBLIC_SITE_URL`. Settings that belong to
   one gateway (such as Cashfree's API version) are part of that account.
2. IF a payment account is configured with a gateway provider and its
   credentials are missing, OR a branch is mapped to an account that is not
   defined, THEN the API SHALL refuse to start with a clear error naming the
   account (never printing a secret).
3. THE secret key SHALL never appear in logs, errors, API responses, the repo, or
   the front end. Only the App ID (not secret) and the mode may reach the
   browser, and only the payment session id is returned to the customer page.
4. ALL outbound Cashfree calls SHALL use HTTPS, an explicit short timeout, and
   no retry that could create a second order for the same attempt.
5. LOGS SHALL contain only the booking reference, our order id and Cashfree ids,
   never phone, email, names, or the raw webhook body.
6. THE webhook route SHALL accept only a bounded body size.
7. Mapping a branch (or the default) to the built-in `manual` account SHALL
   restore today's flow for that branch without a code change or migration.
8. THE customer domain(s) SHALL be whitelisted in the Cashfree dashboard before
   production checkout works (operations task, see tasks).

### R10: Admin visibility

Acceptance criteria:
1. THE admin payment history SHALL show Cashfree payments with method (UPI,
   Card, Other), time, and the Cashfree payment reference.
2. THE admin booking list/edit SHALL show whether a booking was paid online or is
   awaiting manual confirmation.
3. THE existing void, role, and location-access rules SHALL be unchanged.
4. THE admin payment history SHALL show which payment account took each online
   payment.

### R11: Payment accounts per branch (configuration only)

**User story:** As the owner, I want each branch to be able to use its own payment
account or gateway later by changing configuration, so I never have to decide
upfront whether branches share a settlement bank account.

Acceptance criteria:
1. THE configuration SHALL define one or more named **payment accounts**, each with
   a provider (`cashfree` now; others can be added later) and that provider's
   credentials and environment. A built-in account named `manual` always exists.
2. THE configuration SHALL define a **default account** and an optional mapping
   from **branch to account** (keyed by the branch's stable slug). A branch with
   no mapping SHALL use the default.
3. TODAY, all three branches SHALL use the same account by configuring only the
   default. Changing one branch to a different account SHALL need only a
   configuration change and an API restart.
4. THE account used for an order SHALL be stored with the order and with each
   ledger row it produces, so later reconciliation, webhooks and the expiry job
   use the **same** account even if the mapping changes afterwards.
5. EACH account SHALL have its own webhook address (R5.1) and its own signature
   secret. A payment confirmed under one account SHALL NOT be accepted under
   another.
6. THE Cashfree-specific code SHALL live behind the provider interface in a
   single module. Adding another gateway SHALL need a new module plus
   configuration, with no change to the booking, payment-ledger or admin code.
7. EVERY order sent to a gateway SHALL be tagged with the branch, regardless of
   whether branches share an account: the branch name in the order note, and the
   branch slug and booking reference in the order tags, and the order id SHALL
   begin with the booking reference (which carries the branch code).
   **[verify in sandbox]** the tag limits and how they show in the Cashfree
   dashboard.
8. THE branch tag SHALL contain no customer personal data.
9. Per-branch money received SHALL remain reportable from our own data (payment
   to booking to branch) with no extra work.

## Test cases (mandatory, listed explicitly)

**Slot integrity and concurrency**
- T1: Two customers request the same slot at the same time: exactly one booking
  is created, the other gets `409`.
- T2: A pending gateway booking holds the slot (a second request gets `409`);
  after it expires the slot is bookable again.

**Amount and money**
- T3: Online amount = highest matching advance rule; else plan advance; floored
  at ₹500; never above total. Table-driven cases.
- T4: Paise to Cashfree rupee string is exact (50000 -> "500.00", 12345 ->
  "123.45", 1 -> "0.01"), no float drift.
- T5: Client-sent amounts or totals are ignored; the public schema has no amount
  fields.
- T6: Ledger invariants after online payment: due = total - sum(payments), never
  negative display; advance rule satisfied.

**Webhook security and idempotency**
- T7: Valid signature accepted; wrong secret, tampered body, missing headers, or
  modified timestamp all return `401` and change nothing.
- T8: Same success webhook delivered twice: one ledger row, booking accepted
  once, one `accepted` event.
- T9: Concurrent duplicate deliveries: still one ledger row (unique index).
- T10: Out-of-order events: failure after success is ignored; success after
  failure accepts.
- T11: Amount or currency mismatch is recorded as received and handled by the
  advance rule.
- T12: Unknown order id returns `200` and changes nothing.
- T13: Success event with the Get Order confirmation unavailable returns 5xx and
  changes nothing.

**State transitions and audit**
- T14: Success on `pending` gateway booking: ledger row, status `accepted`,
  `payment_recorded` and `accepted` events (null actor), lead updated, email
  scheduled.
- T15: Failed or user-dropped webhook leaves the booking `pending` with the slot
  held; retry via `/pay` creates a new order id.
- T16: Every state change (accepted, expired, reinstated, needs-refund) writes a
  booking event.

**Expiry and reconciliation**
- T17: A gateway booking is not expired before hold + grace.
- T18: Past hold + grace and Cashfree says paid: the job accepts it.
- T19: Past hold + grace and an attempt is in flight: skipped this run.
- T20: Past hold + grace and Cashfree says expired, no success: booking
  `expired`, slot freed.
- T21: Cashfree unreachable during the job: nothing is expired; the next run
  retries.
- T22: The job is idempotent (second run changes nothing). Manual bookings still
  expire at `PENDING_HOLD_MINUTES`.

**Late payment**
- T23: Success on an `expired` booking with the slot still free: reinstated
  `accepted`.
- T24: Success on an `expired` booking whose slot was taken: payment recorded,
  status unchanged, `payment_needs_refund` event, admin banner data present.

**Fallback and manual**
- T25: Cashfree create-order fails: booking kept `pending`, mode `manual`,
  manual instructions returned, never auto-accepted.
- T26: A branch on the `manual` account reproduces today's behaviour exactly. Existing
  tests for create, accept and expiry still pass.
- T27: Accepting a manual booking still requires the recorded advance.

**Access control and config**
- T28: The webhook route needs no login but nothing without a valid signature;
  admin endpoints keep their role and origin checks; `/pay` and status are rate
  limited.
- T29: Missing Cashfree credentials with the provider set to cashfree fail at
  startup.
- T30: Logs and API responses never contain the secret key, raw webhook body, or
  customer contact details.

**Front end (vitest)**
- T31: The status page renders each state (pending, confirmed, failed, expired,
  manual) and polls, then stops.
- T32: Starting payment loads the SDK once, opens checkout with the session id,
  and shows an error with a manual-UPI option if loading fails.
