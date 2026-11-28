# Design: Cashfree online payments

Implements `requirements.md`. Follows `tech.md` and `structure.md`: routers are
thin, services own transactions and rules, integrations wrap the external system
behind the existing `PaymentProvider` interface, money is integer paise.

## 1. How Cashfree works (from the official docs)

- **Create order** (server only): `POST {base}/pg/orders` with headers
  `x-client-id` (App ID), `x-client-secret` (Secret Key), `x-api-version`, and a
  JSON body: `order_id` (ours, unique), `order_amount` (rupees, decimal),
  `order_currency` `INR`, `customer_details` (`customer_id`, `customer_phone`
  required; name/email optional), `order_meta` (`return_url`, `notify_url`), and
  `order_expiry_time`. The response holds `payment_session_id`, `cf_order_id`,
  `order_status` (`ACTIVE`).
  Base URLs: sandbox `https://sandbox.cashfree.com`, production
  `https://api.cashfree.com`.
- **Hosted checkout** (browser): load Cashfree's JS SDK, `Cashfree({mode})`,
  then `cashfree.checkout({ paymentSessionId, redirectTarget })`. `_self`
  redirects the whole page and Cashfree returns the customer to `return_url`.
  The checkout domain must be whitelisted in the dashboard.
- **Do not trust the browser redirect.** Confirm by webhook and by the server
  API (`GET /pg/orders/{order_id}` and `GET /pg/orders/{order_id}/payments`).
- **Webhooks**: Cashfree POSTs JSON to the registered URL. Headers
  `x-webhook-signature`, `x-webhook-timestamp`, `x-webhook-version`,
  `x-webhook-attempt`, and (newer versions) `x-idempotency-key`. Signature =
  base64(HMAC-SHA256(secret, timestamp + rawBody)). Events used: payment
  success, payment failed, payment user dropped. Default retry: 3 times at 2,
  10 and 30 minutes until HTTP 200. Duplicates are possible.
- **Order vs payment lifecycle**: an order is `ACTIVE`, `PAID`, `EXPIRED`,
  `TERMINATED`. A payment is `SUCCESS`, `FAILED`, `PENDING`, `NOT_ATTEMPTED`,
  `FLAGGED`, `CANCELLED`, `VOID`, `USER_DROPPED`. An attempt started before the
  order expiry is honoured until the **Transaction Time Limit** ends, so an
  `EXPIRED` order can still become `PAID`. This drives the grace period and the
  reconcile-before-expire rule.
- **Dashboard settings**: order expiry minimum 5 minutes; Transaction Time Limit
  minimum 10 minutes (we ask for 10).

**[verify in sandbox]** exact `x-api-version` to pin (default `2023-08-01`),
exact webhook payload field names, and the signature on a real sandbox delivery.
Task 1 builds a small script that proves these before the rest depends on them.

## 2. Architecture

```
Customer page (Astro + React island)
   |  POST /public/bookings                     -> CustomerBookingResult
   |  Cashfree JS SDK -> hosted checkout (redirect)
   |  GET  /public/bookings/{token}  (poll)     -> PublicBookingStatus
   |  POST /public/bookings/{token}/pay (retry)
   v
routers/public/bookings.py            routers/webhooks/cashfree.py
   |                                         |
   v                                         v
services/booking.py (create)          services/payment_gateway.py
services/payment_gateway.py  <------- handle_webhook / reconcile / confirm_paid
   |
   v
integrations/payments/{base,manual,cashfree}.py     (only place that talks HTTP)
   |
   v  HTTPS
Cashfree  ----- webhook ----->  VPS (Caddy -> API)
```

`jobs/expire_pending.py` calls `payment_gateway.reconcile_before_expiry`.

## 3. Data model (migration `0027_add_cashfree_payments`)

### `bookings` (new columns)
| column | type | notes |
|---|---|---|
| `payment_mode` | text NOT NULL default `'manual'` | CHECK `IN ('manual','gateway')` |
| `hold_expires_at` | timestamptz NULL | set for gateway bookings only |

Existing rows become `manual` with no migration of data.

### `payment_orders` (new): one row per Cashfree order (attempt)
| column | type | notes |
|---|---|---|
| `id` | bigint identity PK | |
| `booking_id` | bigint FK `bookings.id` ON DELETE CASCADE | index |
| `provider` | text NOT NULL | `cashfree` now |
| `account_key` | text NOT NULL | the payment account used (for example `main`); webhooks, reconcile and the job use **this**, not the current branch mapping |
| `provider_order_id` | text NOT NULL | UNIQUE (`uq_payment_orders_provider_order`); ours, `<booking_reference>-<attempt>` (the reference carries the branch code) |
| `cf_order_id` | text NULL | Cashfree's id |
| `payment_session_id` | text NULL | lets us resume checkout |
| `amount_paise` | bigint NOT NULL | CHECK `> 0` |
| `status` | text NOT NULL | CHECK `IN ('active','paid','failed','expired')` |
| `attempt` | int NOT NULL | 1, 2, 3... |
| `expires_at` | timestamptz NOT NULL | |
| `created_at`, `updated_at` | timestamptz | |

### `payment_webhook_events` (new): processed-event ledger
| column | type | notes |
|---|---|---|
| `id` | bigint identity PK | |
| `provider` | text NOT NULL | |
| `account_key` | text NOT NULL | |
| `event_key` | text NOT NULL | UNIQUE with (provider, account_key); `<type>:<cf_payment_id>:<payment_status>` |
| `provider_order_id` | text NULL | |
| `outcome` | text NOT NULL | `applied`, `duplicate`, `ignored`, `late_refund_needed`... |
| `received_at` | timestamptz default now | |

No raw payload stored (it contains customer details).

### `payments` (one new column and an index)
- New nullable column `provider_account` (text): the payment account that took
  the money, shown in admin payment history.
- Add partial unique index `uq_payments_provider_ref` on `(provider,
  provider_account, provider_ref)` WHERE `provider_ref IS NOT NULL`. Including
  the account means two accounts can never collide on an id, while a repeat
  under the same account is idempotent. Cashfree rows set
  `provider='cashfree'`, `provider_account=<account key>`,
  `provider_ref=<cf_payment_id>`, `recorded_by_user_id` NULL.
- Method maps into the existing CHECK: Cashfree group `upi` -> `upi`; credit or
  debit card -> `card`; everything else -> `other`.

### `booking_events` CHECK
Extend `ck_booking_events_type` (drop and recreate, as migration 0015 did) with
`payment_failed` and `payment_needs_refund`.

All constraints are named. Downgrade drops the tables, columns, index and
restores the earlier CHECK.

## 4. Backend components

### 4.1 `integrations/payments/base.py` (interface change)

The current Protocol returns a string. It becomes richer, and `ManualProvider`
is adapted (its instructions text moves into the result).

```python
@dataclass(frozen=True)
class OrderRequest:
    provider_order_id: str
    booking_reference: str
    amount_paise: int
    customer_id: str          # booking reference; no PII
    customer_phone: str
    customer_name: str | None
    customer_email: str | None
    return_url: str
    notify_url: str
    expires_at: datetime

@dataclass(frozen=True)
class OrderResult:
    provider_order_id: str
    cf_order_id: str | None
    payment_session_id: str | None
    instructions: str | None   # manual provider only

@dataclass(frozen=True)
class GatewayPayment:
    provider_ref: str          # cf_payment_id
    status: Literal["success", "failed", "pending", "dropped", "other"]
    amount_paise: int
    currency: str
    method: str                # upi | card | other
    paid_at: datetime | None

@dataclass(frozen=True)
class OrderStatus:
    provider_order_id: str
    state: Literal["active", "paid", "expired", "terminated", "unknown"]
    payments: list[GatewayPayment]

@dataclass(frozen=True)
class WebhookEvent:
    event_key: str
    kind: Literal["success", "failed", "dropped", "ignored"]
    provider_order_id: str | None
    payment: GatewayPayment | None

class PaymentProvider(Protocol):
    name: str
    def create_order(self, req: OrderRequest) -> OrderResult: ...
    def get_order(self, provider_order_id: str) -> OrderStatus: ...
    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> WebhookEvent: ...
```

`get_payment_provider(account_key)` returns the provider instance for a payment
account (see 4.6); `resolve_account(location)` returns the account key for a
branch. Errors raise
`GatewayUnavailableError` (network, timeout, 5xx, 401/403 from Cashfree) and
`GatewayRejectedError` (4xx validation), both subclasses of `AppError` so
services translate them, never routers.

### 4.2 `integrations/payments/cashfree.py`

- Uses `httpx` (sync client, `timeout=httpx.Timeout(10, connect=5)`, no
  automatic retries). **Dependency note:** `httpx==0.28.1` moves from dev
  dependencies to runtime dependencies; it is already pinned for tests, small, and
  avoids hand-rolling HTTP with `urllib`. No new service or memory cost.
- The provider is constructed **per payment account** (App ID, secret, API
  version and environment come from that account's config). Base URL from the
  account's `ENV`. Headers: `x-client-id`, `x-client-secret`,
  `x-api-version`, `Content-Type`.
- `create_order`: builds the body. `order_amount` is a string produced from
  `Decimal(paise) / 100` quantized to 2 places; never a float. `order_meta`
  carries `return_url` and `notify_url`. `order_expiry_time` is `expires_at` in
  ISO 8601 with the IST offset.
- `get_order`: `GET /pg/orders/{id}` then `GET /pg/orders/{id}/payments`; maps
  Cashfree statuses to our small enums.
- `verify_webhook`: signature check with `hmac.compare_digest` on
  `base64(hmac_sha256(secret, timestamp + raw_body))`; then parse JSON into a
  `WebhookEvent`. Unknown `type` becomes `kind="ignored"`.
- The secret is held in the provider instance only, never logged or returned.

### 4.3 `services/payment_gateway.py` (all rules live here)

| function | purpose |
|---|---|
| `online_advance_paise(booking_total, resolved_advance)` | floor at `ONLINE_ADVANCE_MIN_PAISE`, cap at total |
| `start_checkout(db, booking)` | resolve the branch's account (first attempt) or reuse the account stored on the previous order; create a `payment_orders` row + gateway order, tagged with the branch; return session info |
| `begin_gateway_booking(...)` | called by `create_customer_booking` after commit; on `GatewayUnavailableError` flips the booking to manual (R1.3) |
| `confirm_paid(db, booking, payment, source)` | the single place that records the payment and accepts, in one transaction; idempotent |
| `handle_webhook(db, raw, headers)` | verify, de-duplicate, confirm via `get_order`, then `confirm_paid` or record failure |
| `reconcile_booking(db, booking)` | fetch order status and apply the same outcomes (used by status read and the job) |
| `reconcile_before_expiry(db)` | job entry: for gateway bookings past hold + grace |

**`confirm_paid` (the key transaction):**
1. `SELECT ... FOR UPDATE` the booking row (serialises concurrent webhooks and
   the job).
2. Insert the `Payment` row with `(provider='cashfree', provider_ref)`. On unique
   violation, treat as already processed and stop (idempotent).
3. Write `payment_recorded` event.
4. Branch on status:
   - `pending`: set `accepted`, write `accepted` event (null actor,
     `{"via": "cashfree"}`), `leads_service.on_booking_status_changed`.
   - `accepted`: nothing more.
   - `expired`: re-run `_assert_no_overlap`; if free, set `accepted` and write an
     `edited` event noting reinstatement; else write `payment_needs_refund`.
   - `rejected` / `cancelled`: write `payment_needs_refund`.
5. Update the matching `payment_orders.status`, commit.
6. The caller schedules the confirmation email after commit (only when the
   booking became `accepted` in this call).

Acceptance does not call `accept_booking` (which needs a staff actor). A small
shared helper sets the status and writes the event for both paths so the audit
format stays identical.

**Webhook ordering rules:** failure events only mark the matching
`payment_orders` row `failed` and write `payment_failed`; they never touch a
booking that is `accepted`. A success always goes through `confirm_paid`.

### 4.4 Expiry job

`expire_pending_bookings` keeps its current query for manual bookings
(`payment_mode='manual'`, `created_at + PENDING_HOLD_MINUTES`). A second
pass handles gateway bookings:

```
for booking in pending gateway bookings where hold_expires_at + grace < now:
    provider = get_payment_provider(latest_order.account_key)   # the order's own account
    try:  status = provider.get_order(latest order)
    except GatewayUnavailableError: continue          # never expire on unknown
    if paid:       confirm_paid(...)                  # accept
    elif in flight: continue
    else:          set expired + event; mark order expired
```

Both passes stay idempotent. `python -m app.jobs.expire_pending` stays the entry
point (cron, every minute).

### 4.5 Routers and schemas

- `POST /api/v1/public/bookings` (existing): `CustomerBookingResult` gains
  `payment_mode` (`gateway` | `manual`), `payment_session_id` (nullable),
  `gateway_mode` (`sandbox` | `production`, nullable; the SDK needs it),
  `online_amount_paise`,
  `hold_expires_at`, `gateway_unavailable` (bool). `payment_instructions`
  stays for the manual channel.
- `POST /api/v1/public/bookings/{token}/pay` (new, rate limited 5/min): returns
  session info for a `pending` gateway booking within its hold.
- `GET /api/v1/public/bookings/{token}` (existing): `PublicBookingStatus` gains
  `payment_mode`, `payment_state` (`none|pending|paid|failed|expired|manual`),
  `advance_paise`, `hold_expires_at`, `can_retry`. May reconcile at most once
  per ~5 seconds per booking (in-process timestamp is not allowed to be the only
  guard; use `payment_orders.updated_at`).
- `POST /api/v1/webhooks/{provider}/{account}` (new `routers/webhooks/gateway.py`;
  for example `/api/v1/webhooks/cashfree/main`): looks up the account (unknown
  provider or account returns `404`), verifies with **that account's** secret,
  reads the raw body, size capped, calls `payment_gateway.handle_webhook`,
  returns `200` for applied, duplicate, ignored, unknown-order; `401` for a bad
  signature; `503` when confirmation could not be completed. Registered in
  `main.py`; no `require_role`, no `check_origin`; excluded from rate limiting
  defaults.
- Admin read schemas gain `payment_mode` (booking list/detail) and the payment
  rows already expose `provider` and `provider_ref`. The booking detail gains a
  derived `needs_refund` boolean (status not active and paid total > 0).

### 4.6 Configuration: payment accounts per branch (`core/payment_config.py`)

Accounts are defined in the environment, because secrets never go in the
database or the admin. A small loader reads variables named
`PAYMENT_ACCOUNT_<KEY>_<FIELD>` at startup into a registry. The built-in
`manual` account always exists.

```
# Which account a branch uses when it has no mapping of its own
PAYMENT_DEFAULT_ACCOUNT=main

# One block per account (add another block for another account or gateway)
PAYMENT_ACCOUNT_MAIN_PROVIDER=cashfree        # cashfree | manual | (future gateways)
PAYMENT_ACCOUNT_MAIN_ENV=sandbox              # sandbox | production
PAYMENT_ACCOUNT_MAIN_APP_ID=
PAYMENT_ACCOUNT_MAIN_SECRET_KEY=
PAYMENT_ACCOUNT_MAIN_API_VERSION=2023-08-01

# Optional: branch slug -> account. Unlisted branches use the default.
# PAYMENT_BRANCH_ACCOUNTS=hulimavu:main,ecity:second,jpnagar:main

GATEWAY_HOLD_MINUTES=15
GATEWAY_GRACE_MINUTES=10          # >= the dashboard Transaction Time Limit (10)
ONLINE_ADVANCE_MIN_PAISE=50000
PUBLIC_SITE_URL=https://cinematiccelebration.in
```

Today all three branches use `main`, so only the default and one account block
are needed. Moving a branch to its own account later means adding another block
(`PAYMENT_ACCOUNT_SECOND_*`), adding one entry to `PAYMENT_BRANCH_ACCOUNTS`,
registering that account's webhook address in its dashboard, and restarting.
No code change and no database change.

Rules enforced at startup (the API refuses to start otherwise, without printing
any secret): every gateway account has the fields its provider needs; the
default account exists; every account named in the branch mapping exists.
A branch slug that matches no branch is logged as a warning.

The branch is resolved at booking time from `locations.slug`. The account key is
then copied onto the `payment_orders` row, so changing the mapping later never
re-routes an order already in flight (R11.4).

Providers are looked up in a small registry (`{"cashfree": CashfreeProvider,
"manual": ManualProvider}`). A future gateway is one new module added to that
registry.

`MANUAL_UPI_VPA` stays.

### 4.7 Branch tagging

Every Cashfree order carries the branch, independent of account:
- `order_id`: `<booking_reference>-<attempt>`. **[verify in sandbox]** allowed
  characters and maximum length of an order id.
- `order_note`: `<Branch name> | <booking reference>`.
- `order_tags`: `{"branch": "<slug>", "booking_ref": "<reference>"}`.
  **[verify in sandbox]** tag count and length limits, and whether they are
  searchable or shown in reports in the dashboard.
- No phone, email, name or any other personal data in these fields.

Per-branch money received inside our own system needs no extra work: each payment
belongs to a booking and each booking to a branch (existing analytics by branch).

## 5. Front end

### Customer site (`apps/web`)
- `lib/api.ts`: extend `BookingResult` and `BookingStatus`; add `payBooking(token)`.
- `lib/cashfree.ts` (new): `startCheckout(sessionId, mode)` injects the Cashfree
  SDK `<script>` once on demand, calls `Cashfree({mode}).checkout({paymentSessionId,
  redirectTarget: '_self'})`. Failure to load shows the manual UPI option. Kept
  out of the main bundle so the booking page stays under the 150 KB budget.
- `BookingWizard.tsx`: after create, if `payment_mode==='gateway'` go
  straight to checkout; if `manual`, show today's confirmation card with a short
  note when `gateway_unavailable` is true.
- `BookingStatus.tsx`: render the states in R6, poll every 3 seconds for up to
  2 minutes while the payment state is unresolved, show a countdown to
  `hold_expires_at`, a "Pay now / Try again" button calling `/pay`, and the manual
  instructions for the manual channel.
- Privacy policy: add a line that payments are processed by Cashfree and we do
  not store card or UPI details.

### Admin (`apps/admin`)
- Payment history already lists `provider`; show "Cashfree" and the reference.
- Booking list and edit show a small "Paid online / Awaiting manual payment"
  label.
- Booking edit shows the "Payment received on an inactive booking" banner when
  `needs_refund` is true.

## 6. Failure modes

| situation | behaviour |
|---|---|
| Cashfree down at booking time | booking kept, mode `manual`, manual UPI shown, no auto-accept |
| Customer closes the tab before paying | slot held until `hold_expires_at + grace`, then released after a Cashfree check |
| Customer pays then loses connection | webhook (or status poll, or job) accepts the booking |
| Webhook delayed or lost | status read and expiry job reconcile via Get Order |
| Duplicate or replayed webhook | unique `(provider, provider_ref)`; second call is a no-op |
| Forged webhook | rejected by signature; success is also confirmed via Get Order |
| Payment after slot released | reinstated if free, else flagged for manual refund |
| Customer double-clicks Pay | unique order ids per attempt; `/pay` resumes the active order |
| Amount mismatch | recorded as received, normal advance rule decides |

## 7. Rollout

1. Build and test with fakes and signed fixture payloads (no Cashfree needed).
2. Sandbox end to end in the **Codespace**, not on the live VPS
   (the `main` account with `ENV=sandbox`). Cashfree must reach our
   webhook over public HTTPS, so the API port is forwarded with **public**
   visibility and that URL is registered in the **sandbox** dashboard. Running
   sandbox on the production VPS is avoided because real customers would be sent
   to a test checkout.
3. Whitelist the production domain, enter production keys, set
   the account's `ENV=production`, and run one small real payment, then refund
   it by hand in the dashboard.
4. Rollback at any time: map the branch (or the default) to the `manual` account
   and restart the API.

## 8. Cost and memory

No new container or service. One outbound HTTPS client per request. Cashfree
charges a per-transaction fee (see your Cashfree plan); that is the only cost
impact. API memory impact is negligible.
