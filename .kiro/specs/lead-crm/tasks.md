# Implementation Plan — Lead CRM

Tasks are ordered so the schema and the server rules land first (with tests),
then the booking hooks, then the public API and customer site, then the admin
screens. Optional sub-tasks are marked with `*`.

> Migration numbering: the live DB is at **0023**. This spec adds one revision,
> **0024**, chaining off 0023. Bookings, pricing, availability and payment rules
> are not changed.

- [x] 1. Schema: leads, lead activities, enquiry codes, branch WhatsApp number
  - [x] 1.1 Add `models/lead.py` with `Lead`, `LeadActivity`, `EnquiryCode` and the
    value tuples (`LEAD_STATUSES`, `LEAD_SOURCES` incl. reserved `instant_form`,
    `LEAD_CHANNELS`, `CLOSE_REASONS`, `ACTIVITY_TYPES`); declare every CHECK, FK
    (explicit `ON DELETE`), unique constraint and index from the design in the
    models (tests use `create_all`), including the partial unique index
    `uq_leads_prebooking_phone` on `(location_id, phone)` where status in
    (`new`,`contacted`,`follow_up`) and the CHECKs `ck_leads_closed_has_reason` /
    `ck_leads_closed_no_follow_up`; register in `models/__init__.py`
  - [x] 1.2 Add `Location.whatsapp_phone` (TEXT NULL)
  - [x] 1.3 Migration `0024_create_leads_crm`: create the three tables with explicit
    constraint/index names, add `locations.whatsapp_phone`; downgrade drops them
    (leaves `contact_leads` untouched)
  - [x] 1.4 Add `services/lead_migration.py` `copy_contact_leads(connection)`:
    normalise phones to 10 digits, skip invalid ones (count logged), assign the
    first active branch, create `contact_form` leads with the original
    `created_at`, add the message (+ email, "Branch unknown (migrated)") as the
    first `note`, and attach repeat phones to the first lead; call it from 0024
    `upgrade()`
  - [x] 1.5 Add `LEAD_AUTO_CLOSE_DAYS` (default 0, 0–365) and
    `LEAD_RESPONSE_ALERT_MINUTES` (default 10, 1–1440) to `core/config.py`; list
    both in `.env.example` with one-line explanations
  - [ ] 1.6 Verify 0024 upgrade + downgrade on a seeded DB copy (with some
    `contact_leads` rows)
  - [x] 1.7 Integration test for `copy_contact_leads`: rows become `contact_form`
    leads with the original time and a first note; invalid phones are skipped;
    repeat phones attach to one lead
  - _Requirements: 1.1–1.10, 3.9–3.11, 11.6, 14.7, 16.5, 19.15, A6, A13_

- [x] 2. Pure helpers: phone normalisation and Channel rules
  - [x] 2.1 Add `normalise_to_10_digits(raw) -> str | None` to `core/phone.py`
    (spaces, dashes, leading `0`, `+91`/`91`)
  - [x] 2.2 Add `services/lead_channel.py`: `Attribution` dataclass,
    `clean_attribution()` (trim, strip query/fragment from landing path and
    referrer, drop own-site referrer, never raises), `derive_channel()` (R17.9
    rules, first match wins), `manual_channel(source)`
  - [x] 2.3 Unit tests: one case per Channel (fbclid, gclid, `google`/`gbp`, Google
    referrer, Instagram referrer, Facebook referrer, unknown referrer, empty,
    `whatsapp_ad` → `meta_ads`, `phone` → `manual`)
  - [x]* 2.4 Hypothesis properties: Channel determinism and priority (property 1),
    sanitised paths contain no `?`/`#` and respect length limits (property 2),
    phone formatting variants normalise to the same 10 digits (property 3)
  - _Requirements: A2, 4.4, 4.7, 17.7–17.9, 19.19_

- [x] 3. Lead service core rules (`services/leads.py`, `schemas/lead.py`)
  - [x] 3.1 Schemas: `AttributionIn` (max lengths), `WebsiteLeadIn`, `EnquiryIn`
    (with honeypot `website`), `EnquiryCodeIn`, `LeadTokenOut`, `OkOut`,
    `LeadCreate`, `LeadUpdate`, `ActivityCreate`, `LinkCodeIn`, `LeadListItem`,
    `LeadRead`, `ActivityRead`, `LeadCounts`, `LeadDashboard`, `LeadCreateResult`;
    `extra="ignore"` on public inputs; wrap validator that turns malformed
    `attribution` into `None`; add `app.schemas.lead` to `_rebuild_schemas()`
  - [x] 3.2 `_add_activity` (sets `last_activity_at`) and `_transition` (single place
    that changes status: writes `status_change`, clears `follow_up_at` on close,
    requires a close reason, sets `first_contacted_at`, rejects manual
    `booked`/`won` with 422)
  - [x] 3.3 `_find_or_create_lead`: lock and attach to a pre-booking open lead
    (system activity, fill empty fields only); else attach a new enquiry to a
    `booked` lead; else `INSERT ... ON CONFLICT DO NOTHING` on the partial index
    and re-select on conflict
  - [x] 3.4 Lead_Token: `secrets.token_urlsafe(24)`, store SHA-256 hash; accept only
    for an open, unlinked lead created within 7 days
  - [x] 3.5 `capture_website_lead` (create or update by token, attribution and
    Channel kept from creation), `create_enquiry_lead`, `register_enquiry_code`
    (upsert: first insert keeps attribution, later ones update branch and
    `last_seen_at`), `create_manual_lead` (manual Channel or code Channel, optional
    first note and follow-up), `add_activity` (call/whatsapp on `new` →
    `contacted`), `update_lead` (status/reason/assignment/follow-up/name; follow-up
    on `new`/`contacted` → `follow_up`), `link_enquiry_code` (case-insensitive,
    warning when unknown/expired, notice when used by another lead)
  - [x] 3.6 Integration tests: duplicate rule incl. concurrent creates from two
    sessions; close rules; manual `booked`/`won` rejected; call/WhatsApp →
    `contacted` + `first_contacted_at`; enquiry-code linking (copy attribution,
    unknown/expired warning, reused-code notice)
  - [ ]* 3.7 Hypothesis state-machine test: at most one pre-booking lead per phone
    and branch, activities append-only, `last_activity_at` monotonic, status
    invariants (properties 4–6)
  - _Requirements: 1.5–1.9, 2.2, 2.3, 2.7, 2.13, 4.2, 4.3, 4.7, 4.8, 6.1–6.5, 7.3–7.7,
    17.8, 17.10, 18.5, 18.8–18.11, 19.9–19.11, 19.21_

- [x] 4. Booking hooks: lead follows its booking
  - [x] 4.1 `_lead_savepoint(db, code)` context manager (savepoint, rollback only
    the savepoint, log `lead_hook_failed` with code only)
  - [x] 4.2 `link_public_booking`: link by token, else `_find_or_create_lead`
    (source `website`), set `booked`, `booking_linked` activity; call it in
    `create_customer_booking` after the `created` event and before commit, inside
    the reference-retry loop; add optional `lead_token` to `BookingCreate`
  - [x] 4.3 `link_admin_booking`: add optional `lead_id` to `AdminBookingCreate`;
    validate (same branch, open, unlinked) at the top of `create_admin_booking`
    returning 422; link before commit; `won` when the booking is created accepted
  - [x] 4.4 `on_booking_status_changed`: accepted → `won`; rejected/expired/cancelled
    → `follow_up` with `follow_up_at = now` and a system note; review (expired →
    pending) → `booked`; no-op when no linked lead; call it in `accept_booking`,
    `reject_booking`, `cancel_booking`, `review_booking`, and per booking inside
    `expire_pending_bookings`
  - [x] 4.5 Integration tests: booking with token links and sets `booked`; without
    token creates a linked `booked` lead; accept → `won`; reject/cancel/expire →
    `follow_up`; review → `booked`; admin create without lead creates no lead;
    convert links; invalid `lead_id` → 422 before the booking exists; a slot `409`
    links nothing
  - [x] 4.6 Failure-isolation test: monkeypatch the link/transition helper to raise;
    booking create, accept, reject, cancel, review and expiry still succeed with
    unchanged status, events and payments, and the log has the error code only
  - _Requirements: 2.8–2.11, 8.1–8.7, 9.3, 9.4, 9.6, 16.1, 16.2, 19.4–19.8_

- [x] 5. Public API
  - [x] 5.1 `routers/public/leads.py`: `POST /leads` (10/min), `POST /enquiries`
    (5/min, honeypot returns success and stores nothing), `POST /enquiry-codes`
    (10/min, 204); register in `main.py`
  - [x] 5.2 Update `POST /contact` to create a `contact_form` lead (email and
    `location_id` optional, first active branch with note when missing); stop
    writing `contact_leads`
  - [x] 5.3 Add `whatsapp_phone` to public `LocationRead` and its mapper
  - [x] 5.4 Integration tests: Step 1 capture returns a token and a second call
    updates the same lead; invalid phone 422 and no lead; client status/notes
    ignored; enquiries and contact create leads; honeypot stores nothing; 429 over
    the limits; enquiry-code register/re-register/invalid format; no lead data in
    any public response
  - [x] 5.5 Logging test: lead endpoint logs contain no phone or name
  - _Requirements: 2.1–2.3, 2.12–2.14, 3.2, 3.3, 3.7, 3.11, 12.6, 15.2, 15.3, 18.5–18.7,
    19.2, 19.3, 19.14, 19.16, 19.21_

- [x] 6. Admin API
  - [x] 6.1 `routers/admin/leads.py` with router-level
    `require_role("admin","staff")` + `check_origin`: list (filters incl. channel,
    search ≥ 3 chars, section ordering, pagination), counts (uncontacted, overdue,
    due today), follow-ups digest data, create, detail (timeline, same-phone leads
    limited to accessible branches), update, add activity, link enquiry code,
    assignable users; dashboard with route-level `require_role("admin")`; register
    in `main.py`; branch access via `assert_location_access` in the service
  - [x] 6.2 Dashboard aggregates: per day by source/channel, totals and won per
    source/channel, average and median first response, close reasons, campaigns,
    WhatsApp code share
  - [x] 6.3 Add optional `whatsapp_phone` to `LocationHoursUpdate`,
    `LocationAdminRead` and `to_location_admin_read` (validated Indian mobile,
    `null` clears)
  - [x] 6.4 Access-control tests: 401 without session; staff 403 on another branch's
    lead, 200 on own; staff 403 on dashboard; admin 200; assignment to a user
    without branch access 422
  - [x] 6.5 Tests for list ordering (uncontacted → overdue → due today → new →
    others), uncontacted rule with `LEAD_RESPONSE_ALERT_MINUTES`, counts, and
    dashboard figures on seeded data
  - [x] 6.6 Regenerate `apps/api/openapi.json` and the admin `src/api/schema.ts`
    (`npm run gen:api`)
  - _Requirements: 5.1–5.4, 5.8, 5.9, 6.3, 7.1, 7.2, 7.5, 10.1, 10.2, 11.2, 11.6, 12.1–12.5,
    12.7, 13.1–13.8, 17.11, 18.13, 19.12, 19.22_

- [x] 7. Auto-close job
  - [x] 7.1 `close_stale_leads(db, now, days)`: return 0 when `days == 0`; otherwise
    lock and close stale `new`/`contacted`/`follow_up` leads with no future
    follow-up as `lost`/`no_response` with a system activity; one commit
  - [x] 7.2 `jobs/auto_close_leads.py` (mirrors `expire_pending.py`, logs the count
    only) and the daily 03:00 IST line in `deploy/cron/crontab`
  - [x] 7.3 Integration tests: with 14 days stale leads close; `booked` and future
    follow-up stay open; second run changes nothing; with 0 nothing closes
  - [x]* 7.4 Hypothesis idempotence property (property 8)
  - _Requirements: 14.1–14.8, 16.3, 19.13_

- [x] 8. Customer site: landing attribution and enquiry codes
  - [x] 8.1 `lib/landing.ts` (Landing_Store `cc.landing.v1`: capture on every page,
    campaign params replace, plain visits keep, 30-day expiry, no query strings, no
    PII, storage errors swallowed) and a bundled `<script>` in `Base.astro` that
    runs it on every page
  - [x] 8.2 `lib/enquiry-code.ts` (6-char unambiguous code, reused for 30 days) and
    `lib/whatsapp.ts` (`buildWhatsappLink` using `whatsapp_phone ?? phone`,
    message with "Enquiry code: <code>", `registerEnquiryCode` via keepalive fetch)
  - [x] 8.3 Convert the floating WhatsApp script in `Base.astro` from `is:inline`
    to a bundled script using the helpers; update `LocationList.tsx` WhatsApp links;
    WhatsApp opens even if registration fails
  - [x] 8.4 Add `whatsapp_phone` to the web `Location` type; add
    `normaliseIndianMobile` to `lib/phone.ts`
  - [x] 8.5 Vitest: `landing.test.ts` (homepage UTM then `/book` keeps it; plain
    revisit keeps; new campaign replaces; 30-day expiry; no query strings;
    storage unavailable); `enquiry-code.test.ts` and `whatsapp.test.ts` (code in
    message, reuse, opens on failure, no phone/name in the body)
  - _Requirements: 17.1–17.7, 18.1–18.4, 18.14, 19.20, 19.23_

- [x] 9. Customer site: booking wizard lead capture and enquiry forms
  - [x] 9.1 `lib/lead-capture.ts` (`sendStep1Lead` fire-and-forget, `cc.leadToken`
    in sessionStorage, never throws; `getLeadToken`); `publicApi.createLead`,
    `publicApi.submitEnquiry`, `publicApi.registerEnquiryCode`; `lead_token` on the
    web `BookingCreate` type
  - [x] 9.2 `BookingWizard.tsx`: call `sendStep1Lead` in the Next handler when
    `step === 1` before `setStep`; add `lead_token` to the `createBooking` body;
    helper line under the phone field
  - [x] 9.3 `QuickEnquiry.tsx` on the homepage (`client:visible`): name, phone,
    branch, optional date and message, honeypot, field errors kept on failure,
    success message with branch tap-to-call
  - [x] 9.4 `ContactForm.tsx`: add branch, make email optional, honeypot, field
    errors; post to `/public/enquiries`; helper line under phone
  - [x] 9.5 Privacy policy paragraph (contact details stored to contact the
    customer; enquiry code in WhatsApp links; no message content collected)
  - [x] 9.6 Vitest: Next sends the lead without blocking; failed lead request does
    not block; token reused; booking body includes the token; QuickEnquiry and
    ContactForm submit, field errors, honeypot not visible
  - [x] 9.7 `npm run build` and confirm the booking page stays at or below 150 KB
    gzipped
  - _Requirements: 2.1, 2.4–2.6, 2.8, 2.15, 3.1, 3.4–3.6, 3.8, 15.4, 15.5, 16.4, 19.17_

- [x] 10. Admin panel: leads list, quick-add and navigation
  - [x] 10.1 `features/leads/types.ts`, `lead-queries.ts` (incl. `useLeadCounts`
    with 60 s refetch and refetch on focus), `lead-schema.ts`,
    `lead-filter-state.ts`, `Toast.tsx`
  - [x] 10.2 `LeadsPage.tsx` with sections (Not contacted, Overdue, Due today, New,
    Others), red "Not contacted · N min" label, filters (status, source, channel,
    assignee, dates, search), cards below 768 px and table above, empty state,
    filters kept for the tab
  - [x] 10.3 `QuickAddLeadPage.tsx` (`/leads/new`): phone first with numeric
    keypad, source default WhatsApp incl. "WhatsApp (from ad)", name, branch,
    note, follow-up presets, enquiry code; toast and open the lead, showing any
    code warning or notice
  - [x] 10.4 Routes in `router.tsx` (`leads`, `leads/new`, `leads/dashboard`
    admin-only, `leads/:leadId`); `AppLayout.tsx` Leads nav with `LeadNavBadge`
    (uncontacted pill + overdue/due-today pill) and Lead dashboard nav for admins
  - [x] 10.5 `LocationGate` maps `phone` and `whatsapp_phone`; `LocationSettings.tsx`
    adds the "Branch WhatsApp number" field
  - [x] 10.6 Vitest: quick-add phone normalisation; section ordering and uncontacted
    label; empty state; dashboard nav hidden from staff; badge counts
  - Note: the `leads/dashboard` route, its nav link and the "hidden from staff"
    test land with the dashboard page in group 12 (no placeholder screen). A first
    read-only `LeadDetailPage` ships here so quick-add can open the saved lead;
    group 11 completes it. `follow-up-presets.ts` and `FollowUpPicker.tsx` (11.2)
    are built here because quick-add needs them.
  - _Requirements: 4.1, 4.4–4.6, 4.8, 5.1, 5.2, 5.5–5.10, 10.1, 11.6, 16.6, 19.18_

- [x] 11. Admin panel: lead detail, follow-ups and WhatsApp actions
  - [x] 11.1 `LeadDetailPage.tsx`: contact details, source, Channel and attribution
    summary, linked booking, same-phone leads, enquiry-code link, status /
    close reason / assignee / follow-up editors, `ActivityTimeline`,
    `AddActivityForm`, `CloseLeadDialog` (reason required)
  - [x] 11.2 `follow-up-presets.ts` and `FollowUpPicker.tsx` (1 h, 7 pm, tomorrow
    11 am, +3 days, custom; IST)
  - [x] 11.3 `lead-whatsapp.ts`: `telHref`, `customerWhatsappUrl`,
    `buildFollowUpDigest` (3,500-char cap, "+N more in admin"); `LogContactPrompt`
    after tapping Call or WhatsApp
  - [x] 11.4 "Send today's follow-ups to WhatsApp" on the Leads page, disabled with
    hints when the branch has no number or nothing is due
  - [x] 11.5 Convert to booking: "Create booking" navigates to `/bookings/new` with
    router state; `BookingFormPage` `CreateBooking` passes `initial`, shows the
    lead banner, sends `lead_id`, and links back to the lead; direct visits
    unchanged
  - [x] 11.6 Vitest: digest format, cap and disabled states (property 9 table
    cases); close requires a reason; log-contact prompt; convert pre-fills and
    sends `lead_id`
  - _Requirements: 6.3, 7.1–7.8, 9.1–9.5, 10.3–10.6, 11.1–11.5, 11.7, 18.12, 19.18_

- [x] 12. Admin panel: lead dashboard
  - [x] 12.1 `LeadDashboardPage.tsx` (admin): branch selector, date range (default
    last 30 days), leads per day switchable by source or channel, per-source and
    per-channel totals/won/conversion, first-response average and median, close
    reasons, campaigns table, WhatsApp code share; usable at 360 px
  - [x]* 12.2 Vitest: renders figures from a mocked response and switches grouping
  - _Requirements: 13.1–13.8, 18.13_

- [ ] 13. Final checks
  - [ ] 13.1 Run `ruff`, `pytest`, admin `npm run lint && npm run test && npm run
    build`, web `npm run test && npm run build`; fix failures
  - [ ] 13.2 Update `docs/` with the public allowlist entries for the three new
    public endpoints, and the cron line for the auto-close job
  - _Requirements: 12.6, 14.1, 19.1, 19.24_
