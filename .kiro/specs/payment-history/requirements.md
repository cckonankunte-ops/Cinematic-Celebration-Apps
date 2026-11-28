# Requirements: Payment history and payment channels

## Introduction

Today each payment in the ledger records **how** it was paid (`method`: cash,
UPI, card, other) but not **where the money landed**. The Analytics "Today
income" tab groups by booking and method, so staff cannot list individual
payments or reconcile against the shop QR, the POS machine and so on.

This spec adds:

1. A **payment channel** on every payment: where the money was received.
2. A **Payment history** tab in Analytics: every individual payment, in time
   order, with the date and time it was recorded, filterable by branch, date
   range and channel.
3. A **required channel** (default **Shop QR**) whenever a payment is recorded by
   hand.

It is built **before** the Cashfree spec, which will write the channel
`cashfree` for online payments.

### Decisions (confirmed by the owner)

1. Channels: **Cash, Shop QR, POS machine, Advance QR, Cashfree online, Other.**
2. Payment history is visible to **admins only**, the same as the rest of
   Analytics.
3. Choosing a channel is **required** when a payment is recorded manually. The
   form defaults to **Shop QR**.
4. Filters: branch, from date, to date (both default to today), and channel.
5. Each payment is a separate row, with its recorded date and time shown.

### Out of scope

- Changing how payments are recorded, voided, or counted in totals.
- Per-staff collection reports (the row shows who recorded it; no grouping).
- Editing the channel of an existing payment (void and re-record instead).
- Cashfree itself (separate spec).

## Glossary

- **Method**: how the customer paid (`cash`, `upi`, `card`, `other`). Unchanged.
- **Channel**: where the money was received. New.
  | value | shown as | meaning |
  |---|---|---|
  | `cash` | Cash | physical cash at the venue |
  | `shop_qr` | Shop QR | UPI scanned at the counter (the physical merchant QR) |
  | `pos` | POS machine | card swipe on the POS terminal |
  | `advance_qr` | Advance QR | the manual UPI advance paid to our UPI ID before arrival |
  | `cashfree` | Cashfree online | UPI or card paid on the website (set by the system only) |
  | `other` | Other | anything else |
  Older payments without a channel are shown as **Not specified**.
- **Reversal**: the negative ledger row created when an admin voids a payment.

## Requirements

### R1: Every new payment carries a channel

**User story:** As the owner, I want to know where each rupee was received, so I
can reconcile each source separately.

Acceptance criteria:
1. THE `payments` table SHALL have a `channel` column. Allowed values SHALL be
   `cash`, `shop_qr`, `pos`, `advance_qr`, `cashfree`, `other`, or empty for
   older rows, enforced by a database CHECK.
2. WHEN a payment is recorded by hand (the Record payment dialog or the advance
   entered when creating a booking), THE system SHALL require a channel and
   SHALL reject the request with `422` if it is missing or invalid.
3. THE value `cashfree` SHALL NOT be accepted from manual recording; only the
   gateway code may write it.
4. THE channel and method SHALL stay consistent for cash: a `cash` method
   requires channel `cash`, and channel `cash` requires method `cash`. Any other
   pairing is allowed (for example POS with UPI).
5. WHEN a payment is voided, THE reversing row SHALL carry the same channel as the
   original, so a void nets to zero within its channel.
6. THE `payment_recorded` and `created` audit events SHALL include the channel.
7. THE channel SHALL be included in the payment read schema used by the booking
   screen, so the booking's payment list shows it.

### R2: Recording a payment in the admin screens

**User story:** As staff, I want the channel pre-selected to the most common one
so recording stays quick.

Acceptance criteria:
1. THE Record payment dialog SHALL show a **Channel** field, required, defaulting
   to **Shop QR**.
2. THE "Advance paid now" section when creating a booking SHALL show the same
   Channel field, defaulting to **Shop QR**, required when an advance amount is
   entered.
3. WHEN the channel changes, THE form SHALL preset the method to the usual one
   (Cash to cash, Shop QR to UPI, POS machine to card, Advance QR to UPI), and the
   user MAY still change the method afterwards.
4. THE channel options SHALL list Cash, Shop QR, POS machine, Advance QR and
   Other. Cashfree online SHALL NOT be offered.
5. THE channel SHALL be shown on each row of the booking's payment list.

### R3: Payment history tab

**User story:** As the owner, I want to see every payment as its own row with the
time it was recorded, for any branch and date range.

Acceptance criteria:
1. THE Analytics page SHALL have a fourth tab, **Payment history**, visible to
   admins only (the page is already admin-gated, and the API SHALL also refuse
   non-admins).
2. THE tab SHALL offer filters: **Branch** (the existing branch selector),
   **From** and **To** dates, both defaulting to today (IST), and **Channel**
   (multi-select chips; none selected means all channels, including Not
   specified).
3. THE list SHALL show one row per ledger entry whose recorded date and time falls
   in the range (IST, from the start of the From day to the end of the To day),
   for the selected branch, **oldest first**, with a stable tie-break by id.
4. EACH row SHALL show: date and time recorded, booking reference (linking to the
   booking), customer name, channel, method, amount in rupees, recorded by, the
   payment reference (for online payments), and the note.
5. A reversal row SHALL be shown as its own row with a negative amount and a
   "Reversal" label; the payment it voided SHALL show a "Voided" label. Nothing
   SHALL be hidden, so the list always adds up to the ledger.
6. "Recorded by" SHALL show the staff username, or the gateway name for online
   payments, or "Migrated" for rows imported from the old system.
7. THE tab SHALL show summary cards: **Total received** (the net sum of the rows,
   reversals included), the number of payments, and one card per channel that has
   rows.
8. THE tab SHALL support an **Export** to Excel with the same rows and filters.
9. THE list SHALL be paginated (default 200 rows per page, with Load more) and
   SHALL state clearly when there are more rows than shown. The summary cards
   SHALL cover the whole filtered range, not just the loaded page.
10. ALL amounts SHALL be integer paise in the API and shown in rupees in the UI.

### R4: Existing data

Acceptance criteria:
1. THE migration SHALL set channel `cash` on existing payments whose method is
   `cash`.
2. THE migration SHALL copy the original's channel onto existing reversal rows.
3. ALL other existing payments SHALL keep an empty channel and be shown as **Not
   specified**.
4. THE migration SHALL NOT change any amount, method, date or booking link.

### R5: No change to existing money reports

Acceptance criteria:
1. THE Today income tab, Slot amount tab and Bookings created tab SHALL produce the
   same figures as before.
2. Ledger invariants SHALL hold: amount due = total minus the sum of payments.

## Test cases (mandatory, listed explicitly)

**Channel rules and ledger**
- T1: Recording a payment without a channel returns `422`; an unknown channel
  returns `422`; `cashfree` from manual recording returns `422`.
- T2: Method `cash` with channel `shop_qr` returns `422`; channel `cash` with
  method `upi` returns `422`; POS with UPI is accepted.
- T3: A valid manual payment stores its channel, and the `payment_recorded`
  event contains it.
- T4: An advance entered at booking creation requires a channel when an amount is
  given, stores it, and records it in the events; an amount without a channel
  returns `422`.
- T5: Voiding a payment creates a reversal with the same channel; the channel
  total nets to zero.
- T6: Ledger invariants after recording and voiding: due = total minus sum.

**Payment history API**
- T7: Only admins can read the history and its export; receptionist and staff
  get `403`; unauthenticated gets `401`.
- T8: Date range uses IST bounds: a payment at 23:59 IST on the To day is
  included; one at 00:00 IST the next day is not; one at 00:00 IST on the From
  day is included.
- T9: Only the selected branch's payments appear; another branch's are excluded.
- T10: The channel filter returns only the chosen channels; an empty filter
  returns all, including rows with no channel.
- T11: Rows are ordered by recorded time, then id.
- T12: Reversal rows appear as separate negative rows; the voided original is
  flagged; the total equals the ledger sum.
- T13: Summary cards equal the sum over the whole filtered range even when the
  page is truncated; per-channel totals add up to the total.
- T14: Pagination returns the correct slices and a `has_more` indicator.
- T15: "Recorded by" shows the username, the gateway name, or "Migrated"
  correctly.
- T16: The export contains the same rows and totals as the list.
- T17: No customer phone or email appears in the response (only the name and
  reference already shown elsewhere in analytics).

**Migration**
- T18: Existing cash payments get channel `cash`; reversals copy the original's
  channel; other rows stay empty; amounts and dates are untouched.
- T19: Upgrade, downgrade and upgrade again succeed on real Postgres.

**Regression**
- T20: Existing Today income, Slot amount and Bookings created tests still pass
  unchanged in their figures.

**Front end (vitest)**
- T21: The Record payment dialog defaults the channel to Shop QR, requires a
  channel, presets the method on change, sends the channel, and does not offer
  Cashfree online.
- T22: The advance section on a new booking shows the channel field defaulting to
  Shop QR and sends it with the advance.
- T23: The Payment history tab renders rows with date and time, shows reversal
  and voided labels, channel chips filter the request, summary cards show
  totals, and Load more fetches the next page.
- T24: A non-admin does not see the tab content (existing admin guard).
