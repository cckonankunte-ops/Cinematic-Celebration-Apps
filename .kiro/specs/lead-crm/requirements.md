# Requirements Document

## Introduction

Cinematic Celebration gets 40–50 new enquiries a day, mostly from Meta ads. Most arrive on the WhatsApp Business app; others start a booking on the website and stop, or use the contact form. Today there is no single place to record them, follow up, or see why they did not book.

This feature adds a **Lead** record and a small CRM for receptionists:

- Website visitors become leads as soon as they finish Step 1 of the booking wizard (phone captured), before they submit a booking.
- Receptionists add WhatsApp, phone and walk-in enquiries as leads in a few seconds from their phone, then keep notes and follow-up dates.
- A lead follows its booking automatically: submitted booking → `booked`, accepted booking → `won`.
- Receptionists see overdue and due-today follow-ups first and can send the day's list to the branch WhatsApp number.
- Admins see a lead dashboard: leads by source, conversion, response time, lost reasons.

Bookings, pricing, availability and payment rules do not change. A lead is a separate record that may link to a booking.

Lead lifecycle:

| Step | Lead status | Booking status |
|---|---|---|
| Step 1 completed on website / lead added by staff | `new` | none |
| Receptionist contacts the customer | `contacted` / `follow_up` | none |
| Customer (or staff) submits the booking | `booked` | `pending` |
| Booking accepted | `won` | `accepted` |
| Linked booking rejected / expired / cancelled | `follow_up` | unchanged |
| Customer declines / never replies | `not_interested` / `lost` | none |

When the payment gateway is added later, a website booking goes straight to `accepted`; the lead goes straight to `won`. No change to this spec's lead flow is needed.

### Assumptions

- A1. "Branch" is a row in `locations`. The branch contact number for the follow-up WhatsApp message is `locations.phone`. A separate optional `locations.whatsapp_phone` is added; when set it is used instead of `locations.phone`.
- A2. Phone numbers are normalised to 10-digit Indian mobile numbers (the existing `isValidIndianMobile` rule) and stored as digits only. Display and links add `+91`.
- A3. A lead token is an opaque random string (at least 128 bits, URL-safe) returned to the browser. It identifies one website lead for updates. It carries no personal data.
- A4. Website leads that never book stay as ordinary leads (`new` until a receptionist acts or the auto-close job closes them).
- A5. Leads are never hard-deleted. They are closed (`lost` / `not_interested`). Merging duplicate leads is out of scope.
- A6. The auto-close threshold (days without activity) is a server setting, environment variable `LEAD_AUTO_CLOSE_DAYS`. Default `0`, which means leads are never auto-closed. Setting it to a positive number of days turns auto-close on. It is not editable from the Admin_Panel.
- A7. Public lead endpoints are rate limited to 10 requests per minute per IP (the contact form keeps its current 5 per minute).
- A8. Note text is limited to 2,000 characters. Name is limited to 120 characters.
- A9. The existing `contact_leads` rows are copied into `leads` with source `contact_form`. New contact form submissions write only to `leads`. The `contact_leads` table is kept unchanged and read-only for rollback and removed in a later release.
- A10. Attribution (utm_*, fbclid, gclid, landing path, referrer) is captured when the visitor first lands on any page, kept in browser storage, and stored on website and form leads. The later `meta-ads-conversion-tracking` spec reuses the same Landing_Store and extends it (`_fbp`/`_fbc`, Meta events); this spec makes no Meta calls.
- A11. Landing attribution is kept for 30 days in browser storage. A later visit that carries campaign parameters (utm_*, fbclid or gclid) replaces it; a later visit without campaign parameters does not.
- A12. Channel rules are a fixed server-side mapping (Requirement 17). They can be refined later without a schema change, because the raw attribution is stored.
- A13. The "not contacted" alert threshold is a server setting, environment variable `LEAD_RESPONSE_ALERT_MINUTES`, default 10 minutes. It is not editable from the Admin_Panel.
- A14. Enquiry_Codes are 6 characters from an unambiguous alphabet (no 0/O, 1/I/L), generated in the browser, and valid for 30 days. A visitor reuses the same code for 30 days.

### Non-Goals

- No Meta Pixel, Conversions API, or any Meta event (separate spec).
- No Instant Forms / Lead Ads webhook (separate spec).
- No WhatsApp Cloud API or automatic capture of WhatsApp messages. The business uses the WhatsApp Business app, so WhatsApp leads are entered manually.
- No email or SMS reminders. Email is not set up.
- No consent banner (to be decided later).
- No back-fill of leads for existing or migrated bookings.
- No "offer for a number" (unlock a coupon by entering a phone) and no exit-intent popup or timed enquiry bar. Both are recorded in `docs/FUTURE_WORK.md`.
- No chat widget, chatbot, phone OTP verification, or call-tracking numbers.
- No merge of duplicate leads, no lead import/export file, no lead deletion.
- No change to booking statuses, pricing, availability, double-booking or payment rules.
- No changes to `Old_Application/`.

## Glossary

- **API**: The FastAPI backend in `apps/api`.
- **Admin_Panel**: The React admin app in `apps/admin`.
- **Customer_Site**: The Astro static site with React islands in `apps/web`.
- **Booking_Wizard**: The customer booking flow (`BookingWizard.tsx`). Step 1 collects plan, time window, guests, name and phone.
- **Lead**: A row in the new `leads` table representing one enquiry from one customer at one branch.
- **Lead_Status**: One of `new`, `contacted`, `follow_up`, `booked`, `won`, `not_interested`, `lost`.
- **Open_Lead**: A Lead whose status is `new`, `contacted`, `follow_up` or `booked`.
- **Closed_Lead**: A Lead whose status is `won`, `not_interested` or `lost`.
- **Lead_Source**: How the enquiry reached us. One of `website`, `homepage_form`, `contact_form`, `whatsapp`, `whatsapp_ad`, `phone`, `walk_in`, `instagram_dm`, `other`. `whatsapp_ad` means a WhatsApp chat that started from a Meta ad. `instant_form` is reserved for the later Lead Ads spec.
- **Channel**: Where the visitor came from, derived by the API from the stored attribution. One of `meta_ads`, `google_ads`, `google_business_profile`, `google_search`, `instagram_organic`, `facebook_organic`, `other_referral`, `direct`, `manual`.
- **Landing_Store**: Customer_Site browser storage that holds the visitor's landing attribution (utm_*, fbclid, gclid, landing path, referrer, timestamp).
- **Enquiry_Code**: A short code (for example `W4K7XQ`) that the Customer_Site puts into the pre-filled WhatsApp message and registers with the API together with the visitor's landing attribution, so a receptionist can link a WhatsApp chat to the ad or page it came from.
- **Uncontacted_New_Lead**: A Lead with status `new`, no `first_contacted_at`, created more than `LEAD_RESPONSE_ALERT_MINUTES` ago.
- **Close_Reason**: One of `price_budget`, `date_not_available`, `booked_elsewhere`, `no_response`, `just_enquiring`, `other`, plus optional free text.
- **Lead_Activity**: An append-only timeline entry on a Lead: `note`, `call`, `whatsapp`, `status_change`, `follow_up_set`, `booking_linked`, `system`.
- **Lead_Token**: The opaque token returned to the browser for a website Lead (assumption A3).
- **Follow_Up**: A date and time on a Lead when a receptionist should contact the customer next.
- **Overdue**: A Follow_Up before now (IST) on an Open_Lead.
- **Due_Today**: A Follow_Up later today (IST) on an Open_Lead.
- **Auto_Close_Job**: The CLI module `python -m app.jobs.auto_close_leads`.
- **Admin_User**: An authenticated user with role `admin`.
- **Staff_User**: An authenticated user with role `staff`, restricted to their assigned branch.

## Requirements

### Requirement 1: Lead data model

**User Story:** As an owner, I want every enquiry stored as one lead record, so that nothing is lost and we can see what happened to it.

#### Acceptance Criteria

1. THE API SHALL store Leads in a new table `leads` created by an Alembic migration after revision `0023`.
2. THE `leads` table SHALL store: id, location_id (foreign key), phone (digits only), name (nullable), source (CHECK on Lead_Source values), status (CHECK on Lead_Status values), close_reason (nullable, CHECK on Close_Reason values), close_reason_text (nullable), assigned_user_id (nullable foreign key), follow_up_at (nullable `timestamptz`), last_activity_at, first_contacted_at (nullable), booking_id (nullable foreign key), lead_token (nullable, unique), enquiry fields (preferred_date, plan_id, start_time, duration_minutes, guests — all nullable), message (nullable), attribution fields (utm_source, utm_medium, utm_campaign, utm_content, utm_term, fbclid, gclid, landing_path, referrer, landed_at — all nullable), channel (CHECK on Channel values), created_at and updated_at.
3. THE migration SHALL declare every foreign key with explicit `ON DELETE` behaviour and explicitly named indexes on (location_id, status), (location_id, follow_up_at), phone, and booking_id.
4. THE API SHALL store Lead_Activities in a new table `lead_activities` with: id, lead_id (foreign key, `ON DELETE CASCADE`), type (CHECK on Lead_Activity types), text (nullable, at most 2,000 characters), author_user_id (nullable foreign key; null for system and customer actions), created_at.
5. THE API SHALL never update or delete a Lead_Activity row.
6. WHEN a Lead's status changes, THE API SHALL write a `status_change` Lead_Activity in the same transaction, recording the old and new status.
7. WHEN a Lead_Activity is written, THE API SHALL set the Lead's `last_activity_at` to the activity time in the same transaction.
8. WHEN a Lead moves to `not_interested` or `lost`, THE API SHALL require a Close_Reason.
9. WHEN a Lead moves to a Closed_Lead status, THE API SHALL clear its `follow_up_at`.
10. THE `bookings` table SHALL NOT receive a new status value.

### Requirement 2: Website lead capture from the booking wizard

**User Story:** As a receptionist, I want customers who start a booking on the website to appear as leads, so that I can call people who stop before submitting.

#### Acceptance Criteria

1. WHEN a customer completes Step 1 of the Booking_Wizard and taps Next, THE Customer_Site SHALL send the Step 1 details (branch, date, plan, time window, guests, name, phone) and the attribution held in the Landing_Store to `POST /api/v1/public/leads`.
2. WHEN the API receives that request without a Lead_Token, THE API SHALL create a Lead with source `website` and status `new`, and SHALL return a new Lead_Token.
3. WHEN the API receives that request with a valid Lead_Token, THE API SHALL update that Lead's enquiry fields and name instead of creating a new Lead.
4. THE Customer_Site SHALL keep the Lead_Token in `sessionStorage` and SHALL send it on later Step 1 submissions in the same browser session.
5. THE Customer_Site SHALL send the lead request without awaiting it before moving to Step 2, so that a slow or failed request never delays or blocks the wizard.
6. IF the lead request fails for any reason, THEN THE Customer_Site SHALL continue the booking flow normally and show no error to the customer.
7. IF the Lead_Token is unknown, expired, or belongs to a Closed_Lead, THEN THE API SHALL create a new Lead, applying the duplicate rule in Requirement 6, and return the new Lead_Token.
8. WHEN the customer submits the booking, THE Customer_Site SHALL include the Lead_Token in the existing `POST /api/v1/public/bookings` request.
9. WHEN the API creates a public booking with a valid Lead_Token, THE API SHALL link the booking to the Lead, set the Lead status to `booked`, and write a `booking_linked` Lead_Activity, in the same transaction as the booking.
10. WHEN the API creates a public booking without a valid Lead_Token, THE API SHALL create a Lead with source `website`, link it to the booking, and set status `booked`, applying the duplicate rule in Requirement 6.
11. IF lead linking fails, THEN THE API SHALL still create the booking and return the existing successful response, and SHALL log an error code with no personal data.
12. THE public lead endpoint SHALL validate the phone with the same rule as the booking form and SHALL return `422` for an invalid phone.
13. THE public lead endpoint SHALL accept only the listed fields and SHALL ignore any status, assignment, note, or reason supplied by the client.
14. THE API SHALL rate-limit `POST /api/v1/public/leads` to 10 requests per minute per IP and return `429` beyond that.
15. THE Customer_Site SHALL place no phone number or name in any URL.

### Requirement 3: Quick enquiry forms on the homepage and contact page

**User Story:** As an owner, I want a short enquiry form on the homepage and the contact page, so that visitors who are not ready to book can still leave their number.

#### Acceptance Criteria

1. THE Customer_Site SHALL show a Quick Enquiry form on the homepage with fields: name, phone, branch, optional preferred date, optional message.
2. WHEN a visitor submits the homepage form with valid data, THE API SHALL create a Lead with source `homepage_form` and status `new`, applying the duplicate rule in Requirement 6.
3. WHEN a visitor submits the existing contact page form, THE API SHALL create a Lead with source `contact_form`, applying the duplicate rule in Requirement 6.
4. THE contact page form SHALL add a branch field, and the email field SHALL become optional.
5. WHEN a quick enquiry is saved, THE Customer_Site SHALL show a success message and the branch phone number with a tap-to-call link.
6. IF a quick enquiry fails validation, THEN THE Customer_Site SHALL show the field errors and keep the entered values.
7. THE quick enquiry endpoints SHALL include a hidden honeypot field, and IF the honeypot is filled, THEN THE API SHALL return the normal success response and store nothing.
8. THE Customer_Site SHALL send the attribution held in the Landing_Store with homepage and contact form submissions, and THE API SHALL store it on the Lead.
9. THE migration SHALL copy every existing `contact_leads` row into `leads` with source `contact_form`, status `new`, the original `created_at`, and the message as the first `note` Lead_Activity.
10. WHEN a contact_leads row has no resolvable branch, THE migration SHALL assign the first active branch and record "branch unknown (migrated)" in the note.
11. THE API SHALL stop writing new rows to `contact_leads`.

### Requirement 4: Manual quick-add for WhatsApp, phone and walk-in leads

**User Story:** As a receptionist, I want to add a WhatsApp chat as a lead in seconds from my phone, so that every enquiry is tracked.

#### Acceptance Criteria

1. THE Admin_Panel SHALL provide a quick-add form reachable in one tap from the Leads page, with: phone (required), source (required, default `whatsapp`, with `whatsapp_ad` labelled "WhatsApp (from ad)"), name (optional), branch (default the selected branch), note (optional), follow-up date and time (optional).
2. WHEN a receptionist saves the quick-add form, THE API SHALL create a Lead with status `new`, or `follow_up` when a follow-up time is given, applying the duplicate rule in Requirement 6.
3. WHEN a note is entered in quick-add, THE API SHALL store it as the first `note` Lead_Activity authored by the user.
4. WHEN a phone number is pasted with spaces, dashes, a leading `0`, or a `+91` prefix, THE Admin_Panel and THE API SHALL normalise it to 10 digits before validation.
5. THE quick-add form SHALL be fully usable at a 360 px wide viewport, with the phone field focused first and a numeric keypad on mobile.
6. WHEN the quick-add succeeds, THE Admin_Panel SHALL show a toast and open the new or matched Lead.
7. WHEN a manual Lead is created without an Enquiry_Code, THE API SHALL set its Channel to `meta_ads` for source `whatsapp_ad` and to `manual` for every other manual source.
8. THE quick-add form SHALL include an optional "Enquiry code" field, and WHEN a valid Enquiry_Code is entered, THE API SHALL apply Requirement 18.

### Requirement 5: Lead list, search and filters

**User Story:** As a receptionist, I want to see who to call first and find any lead quickly, so that no follow-up is missed.

#### Acceptance Criteria

1. THE Admin_Panel SHALL provide a Leads page listing leads for the selected branch, with sections in this order: Overdue, Due Today, New (no follow-up set), then all other leads.
2. THE Admin_Panel SHALL show for each lead: name or phone, source, status, follow-up time, last activity time, and linked booking reference when present.
3. THE API SHALL support filtering by status (multiple), source (multiple), assigned user, follow-up date range, created date range, and text search on name and phone (minimum 3 characters).
4. THE API SHALL paginate the list server-side with a stable sort.
5. THE Admin_Panel SHALL keep the Leads page filters for the browser tab, so that returning from a lead restores them, as on the Bookings page.
6. THE Admin_Panel SHALL render leads as cards below 768 px width and as a table at 768 px or wider.
7. IF no leads match, THEN THE Admin_Panel SHALL show an empty-state message.
8. THE Admin_Panel SHALL place Uncontacted_New_Leads at the top of the Leads page, above Overdue, highlighted with a red "Not contacted · N min" label showing minutes since creation.
9. THE Admin_Panel SHALL include the Uncontacted_New_Lead count in the header badge (Requirement 10), shown distinctly from the follow-up count.
10. WHEN a Lead receives its first contact (Requirement 7.4), THE Admin_Panel SHALL remove the highlight.

### Requirement 6: Duplicate handling by phone

**User Story:** As a receptionist, I want repeat enquiries from the same number to land on the same lead, so that I see the full history.

#### Acceptance Criteria

1. WHEN a Lead would be created for a phone that already has an Open_Lead at the same branch, THE API SHALL attach to that Open_Lead instead, write a `system` Lead_Activity naming the new source, and update empty enquiry fields only.
2. WHEN a Lead would be created for a phone that has only Closed_Leads at the same branch, THE API SHALL create a new Lead.
3. WHEN an Admin_Panel user opens a Lead, THE Admin_Panel SHALL show other Leads with the same phone at any branch the user may access, with status and dates.
4. THE API SHALL perform the duplicate check and the insert so that two simultaneous requests for the same phone and branch produce one Open_Lead.
5. WHEN a duplicate is attached from a public endpoint, THE API SHALL return the same success response as for a new Lead and reveal nothing about existing leads.

### Requirement 7: Lead detail, notes and activity timeline

**User Story:** As a receptionist, I want to read and add notes on a lead, so that anyone can pick up the conversation.

#### Acceptance Criteria

1. THE Admin_Panel SHALL show a Lead detail page with: contact details, source, status, assigned user, follow-up, enquiry details (date, plan, time, guests), Channel, attribution summary (utm_source, utm_medium, utm_campaign, landing path, referrer domain, whether fbclid or gclid was present), linked booking, and the activity timeline newest first.
2. THE Admin_Panel SHALL let a user add a Lead_Activity of type `note`, `call`, or `whatsapp` with optional text.
3. WHEN a user adds a `call` or `whatsapp` activity on a Lead with status `new`, THE API SHALL set the status to `contacted`.
4. WHEN a Lead receives its first `call`, `whatsapp`, or status change away from `new`, THE API SHALL set `first_contacted_at` if it is empty.
5. THE Admin_Panel SHALL let a user change status, Close_Reason, assigned user, and follow-up from the detail page.
6. WHEN a user sets a follow-up on a Lead with status `new` or `contacted`, THE API SHALL set the status to `follow_up` and write a `follow_up_set` Lead_Activity.
7. THE API SHALL reject a manual status change to `booked` or `won` with `422`; those statuses come only from booking links (Requirement 8).
8. THE Admin_Panel SHALL show each activity's type, text, author name (or "Customer" / "System"), and time in IST.

### Requirement 8: Lead follows its booking

**User Story:** As an owner, I want lead status to follow the booking automatically, so that conversion figures are correct without extra clicks.

#### Acceptance Criteria

1. WHEN a booking linked to a Lead is accepted, THE API SHALL set the Lead status to `won` and write a `status_change` Lead_Activity, in the same transaction as the acceptance.
2. WHEN a booking linked to a Lead is rejected, expired, or cancelled, THE API SHALL set the Lead status to `follow_up`, set `follow_up_at` to now, and write a `system` Lead_Activity stating the booking outcome.
3. WHEN a linked booking that was rejected, expired or cancelled is reinstated to `pending`, THE API SHALL set the Lead status back to `booked`.
4. WHEN the pending-expiry job expires a linked booking, THE API SHALL apply criterion 2 in the same job transaction.
5. IF updating the Lead fails, THEN THE API SHALL still complete the booking accept, reject, cancel, reinstate, or expiry, and SHALL log an error code with no personal data.
6. THE API SHALL apply these transitions to any linked booking, whether created by a customer or by staff.
7. WHEN a Lead is `won`, THE API SHALL NOT change its status because of later edits to the booking, except criterion 2 if the booking is later cancelled.

### Requirement 9: Convert a lead to a booking

**User Story:** As a receptionist, I want to create a booking straight from a lead, so that I don't retype details.

#### Acceptance Criteria

1. THE Admin_Panel SHALL show a "Create booking" action on an Open_Lead without a linked booking.
2. WHEN the user selects "Create booking", THE Admin_Panel SHALL open the existing admin booking form pre-filled with the lead's name, phone, branch, preferred date, plan, and guests where present.
3. WHEN the admin booking is saved from a lead, THE API SHALL link the booking to the Lead and set the Lead status to `booked`, or `won` if the booking is saved as `accepted`, in the same transaction as the booking.
4. THE API SHALL use the existing admin booking validation and pricing unchanged.
5. WHEN a Lead already has a linked booking, THE Admin_Panel SHALL show the booking reference with a link instead of "Create booking".
6. WHEN staff create a booking in the Admin_Panel without starting from a lead, THE API SHALL create no Lead.

### Requirement 10: Follow-ups, header badge and quick actions

**User Story:** As a receptionist, I want reminders and one-tap contact, so that I follow up on time from my phone.

#### Acceptance Criteria

1. THE Admin_Panel SHALL show in the header a badge with the count of Overdue plus Due_Today leads for the selected branch.
2. THE API SHALL compute the badge count in a single lightweight endpoint, and THE Admin_Panel SHALL refresh it at most once per minute and on focus.
3. THE Admin_Panel SHALL show for each lead a tap-to-call link `tel:+91<phone>` and a WhatsApp link to `wa.me/91<phone>` with a short greeting message using the customer name and branch name.
4. WHEN a user taps the WhatsApp or call link, THE Admin_Panel SHALL offer to log a `whatsapp` or `call` activity in one tap.
5. THE Admin_Panel SHALL provide quick follow-up presets: in 1 hour, this evening (7 pm), tomorrow 11 am, in 3 days, and a custom date and time.
6. THE Admin_Panel SHALL display all follow-up times in IST.

### Requirement 11: Send today's follow-ups to the branch WhatsApp

**User Story:** As a receptionist, I want today's follow-up list on the branch WhatsApp, so that I can work through it on my phone.

#### Acceptance Criteria

1. THE Admin_Panel SHALL provide a "Send today's follow-ups to WhatsApp" action on the Leads page.
2. WHEN the user selects that action, THE Admin_Panel SHALL open `wa.me/<branch number>` with a pre-filled message listing Overdue and Due_Today leads for the selected branch: name (or "Unknown"), phone with `+91`, follow-up time, status, and the last note truncated to 60 characters.
3. THE branch number SHALL be `locations.whatsapp_phone` when set, otherwise `locations.phone`.
4. IF the branch has no usable number, THEN THE Admin_Panel SHALL disable the action and show "Add a branch WhatsApp number in Location settings".
5. IF the message would exceed 3,500 characters, THEN THE Admin_Panel SHALL include the first leads that fit and end the message with "+N more in admin".
6. THE Admin_Panel SHALL add an optional `whatsapp_phone` field to the existing branch settings, validated as an Indian mobile number.
7. IF there are no Overdue or Due_Today leads, THEN THE Admin_Panel SHALL disable the action and show "No follow-ups due".

### Requirement 12: Assignment and access control

**User Story:** As an owner, I want only receptionists (and admins) to work leads, each on their own branch, so that customer numbers and sales notes stay with the people trained to use them.

> Changed after design approval (owner request): a new **Receptionist** role
> (`receptionist`) has everything Staff can do plus the lead CRM. Staff no longer
> see or change leads. Receptionist_User below means a user with that role.

#### Acceptance Criteria

1. THE API SHALL protect every endpoint under `/api/v1/admin/leads` with `require_role("admin", "receptionist")` applied at router level, and SHALL return `403` to Staff_Users.
2. THE API SHALL enforce branch access in the service layer: Receptionist_Users read and change only Leads of their branch; Admin_Users access all branches.
3. IF a Receptionist_User requests a Lead of another branch, THEN THE API SHALL return `403`.
4. THE API SHALL allow assigning a Lead only to an active Admin_User or an active Receptionist_User of the Lead's branch, and SHALL return `422` otherwise.
5. THE lead dashboard endpoints SHALL be admin-only and SHALL return `403` to Receptionist_Users and Staff_Users.
6. THE public lead endpoints SHALL be listed explicitly in the public route allowlist.
7. IF a request without a valid session reaches an admin lead endpoint, THEN THE API SHALL return `401`.
8. THE API SHALL give Receptionist_Users every permission Staff_Users have (bookings, payments, time and cake sheets, late-booking switch) with the same branch limit and the staff booking-time rules.
9. IF a Staff_User sends an admin booking with `lead_id`, THEN THE API SHALL return `403` and create no booking. Booking status changes made by Staff_Users SHALL still update the linked Lead (Requirement 8).
10. THE Admin_Panel SHALL show the Leads navigation, badge and pages only to Admin_Users and Receptionist_Users, and SHALL let an Admin_User create a Receptionist_User and change an existing user's role and branch. A role change applies from that user's next login.

### Requirement 13: Lead dashboard

**User Story:** As an owner, I want to see where leads come from and how many book, so that I know which channels work.

#### Acceptance Criteria

1. THE Admin_Panel SHALL provide a Lead dashboard for Admin_Users with a branch selector and a created-date range defaulting to the last 30 days.
2. THE dashboard SHALL show leads per day, switchable between grouping by Lead_Source and by Channel.
3. THE dashboard SHALL show, per Lead_Source and per Channel, total leads, won leads, and conversion rate (won ÷ total).
4. THE dashboard SHALL show the average and median first-response time (`first_contacted_at` − `created_at`) for leads contacted in the range.
5. THE dashboard SHALL show a breakdown of Close_Reasons for `lost` and `not_interested` leads.
6. THE API SHALL compute all dashboard figures server-side in aggregate queries.
7. THE dashboard SHALL be usable at a 360 px wide viewport.
8. THE dashboard SHALL show, for leads with a utm_campaign, total and won leads per campaign.

### Requirement 14: Auto-close stale leads

**User Story:** As a receptionist, I want old untouched leads closed automatically, so that my list only shows live enquiries.

#### Acceptance Criteria

1. THE API SHALL provide the CLI module `python -m app.jobs.auto_close_leads` and a schedule entry in `deploy/cron/` that runs it once a day.
2. WHEN the Auto_Close_Job runs, THE Auto_Close_Job SHALL set to `lost` with Close_Reason `no_response` every Lead with status `new`, `contacted` or `follow_up` whose `last_activity_at` is older than `LEAD_AUTO_CLOSE_DAYS` days and whose `follow_up_at` is empty or in the past.
3. THE Auto_Close_Job SHALL NOT close Leads with status `booked`.
4. THE Auto_Close_Job SHALL write a `system` Lead_Activity for each closed Lead.
5. WHEN the Auto_Close_Job runs twice in a row, THE second run SHALL change nothing.
6. THE Auto_Close_Job SHALL log only the number of leads closed.
7. WHILE `LEAD_AUTO_CLOSE_DAYS` is `0` (the default), THE Auto_Close_Job SHALL close no Lead and SHALL exit with status 0.
8. THE Auto_Close_Job SHALL read `LEAD_AUTO_CLOSE_DAYS` at the start of each run, so a changed value applies from the next run.

### Requirement 15: Privacy and logging

**User Story:** As an owner, I want CRM data kept internal, so that customer conversations and our notes stay private.

#### Acceptance Criteria

1. THE API SHALL send no Lead_Activity text, status, Close_Reason, assignment or internal note to any third party.
2. THE API SHALL write no phone number, name, note text or message to logs.
3. THE API SHALL return no Lead data from any public endpoint other than the Lead_Token and a success message.
4. THE Customer_Site privacy policy SHALL state that name, phone and enquiry details entered in the booking form or enquiry forms may be stored and used to contact the customer about their enquiry.
5. THE Customer_Site SHALL show a short line under the phone field in Step 1 and in the enquiry forms: "We'll use this number to help with your booking."
6. THE Admin_Panel SHALL show phone numbers only to authenticated users with access to the Lead's branch.

### Requirement 16: Reliability and compatibility

**User Story:** As an owner, I want the CRM to never break bookings, so that revenue is safe.

#### Acceptance Criteria

1. IF any lead operation fails during a booking request, THEN THE API SHALL complete the booking request with its existing outcome.
2. THE API SHALL keep the existing request and response fields of `POST /api/v1/public/bookings` and accept `lead_token` only as a new optional field.
3. THE API SHALL add no always-running process for leads; the Auto_Close_Job SHALL be a short-lived cron process.
4. THE Customer_Site SHALL keep the booking page JavaScript bundle at or below 150 KB gzipped.
5. THE `.env.example` SHALL list `LEAD_AUTO_CLOSE_DAYS=0` (0 = never auto-close) and `LEAD_RESPONSE_ALERT_MINUTES=10`, each with a one-line explanation.
6. THE Admin_Panel SHALL add Leads (all users) and Lead dashboard (admins) to the existing navigation without removing or renaming existing entries.

### Requirement 17: Landing attribution and channel

**User Story:** As an owner, I want to know where each lead really came from (Meta ads, Google, Instagram, direct), so that I spend on the channels that bring bookings.

#### Acceptance Criteria

1. WHEN a visitor loads any Customer_Site page, THE Customer_Site SHALL read utm_source, utm_medium, utm_campaign, utm_content, utm_term, fbclid and gclid from the URL, and the document referrer.
2. WHEN the Landing_Store is empty, THE Customer_Site SHALL save the landing attribution: those values, the landing path without query string, the referrer when it is not the Customer_Site's own domain, and the time.
3. WHEN a page loads with any utm_*, fbclid or gclid value, THE Customer_Site SHALL replace the Landing_Store contents with the new landing attribution.
4. WHEN a page loads without campaign parameters and the Landing_Store already holds attribution, THE Customer_Site SHALL keep the stored attribution unchanged, including when the visitor navigates between pages.
5. WHEN stored attribution is older than 30 days, THE Customer_Site SHALL treat the Landing_Store as empty.
6. IF browser storage is unavailable, THEN THE Customer_Site SHALL send the current page's attribution only and keep working.
7. THE Customer_Site SHALL store no name, phone or email in the Landing_Store, and SHALL strip the query string from the stored landing path and referrer.
8. THE API SHALL validate attribution fields with maximum lengths, and IF attribution is malformed, THEN THE API SHALL discard it and still save the Lead.
9. WHEN the API saves a website or form Lead, THE API SHALL set the Channel from the stored attribution using these rules, first match wins:
   - `meta_ads`: fbclid present, or utm_source is facebook, fb, instagram, ig or meta (case-insensitive) with utm_medium in paid, cpc, ppc, ad, ads, paid_social.
   - `google_ads`: gclid present, or utm_source is google with utm_medium in cpc, ppc, paid.
   - `google_business_profile`: utm_source is google with utm_medium gbp.
   - `google_search`: referrer domain is a Google domain.
   - `instagram_organic`: utm_source is instagram/ig, or referrer domain is instagram.com or l.instagram.com.
   - `facebook_organic`: utm_source is facebook/fb, or referrer domain is facebook.com, m.facebook.com or l.facebook.com.
   - `other_referral`: any other referrer domain, or a utm_source not matched above.
   - `direct`: no attribution at all.
10. WHEN a website Lead is updated with a Lead_Token, THE API SHALL keep the attribution and Channel recorded when the Lead was created.
11. THE Admin_Panel Leads page SHALL support filtering by Channel.

### Requirement 18: WhatsApp enquiry code

**User Story:** As an owner, I want WhatsApp chats started from the website to carry a code, so that we know which ad or page each chat came from.

#### Acceptance Criteria

1. WHEN a visitor taps any WhatsApp link on the Customer_Site (the floating WhatsApp button and the branch WhatsApp links), THE Customer_Site SHALL pre-fill the WhatsApp message with a greeting and the line "Enquiry code: <Enquiry_Code>".
2. THE Customer_Site SHALL generate the Enquiry_Code in the browser, keep it in browser storage for 30 days, and reuse it for later WhatsApp taps by the same visitor.
3. WHEN a visitor taps a WhatsApp link, THE Customer_Site SHALL register the Enquiry_Code, the branch tapped, and the Landing_Store attribution with `POST /api/v1/public/enquiry-codes` without delaying the opening of WhatsApp (for example using `navigator.sendBeacon`).
4. IF the registration fails or browser storage is unavailable, THEN THE Customer_Site SHALL still open WhatsApp with the pre-filled message.
5. THE API SHALL store each Enquiry_Code once with its attribution, Channel, branch, and created time, in a new table `enquiry_codes` with a unique constraint on the code; a repeated registration of the same code SHALL update the branch and keep the original attribution.
6. THE `enquiry_codes` table SHALL store no name, phone or message text.
7. THE API SHALL rate-limit `POST /api/v1/public/enquiry-codes` to 10 requests per minute per IP and SHALL validate the code format.
8. WHEN a receptionist enters an Enquiry_Code in quick-add or on a Lead's detail page, THE API SHALL look the code up case-insensitively, copy its attribution and Channel onto the Lead, link the code to the Lead, and write a `system` Lead_Activity "Linked enquiry code <code>".
9. IF the Enquiry_Code is unknown or older than 30 days, THEN THE API SHALL save the Lead without attribution and return a warning that THE Admin_Panel SHALL show, without failing the save.
10. WHEN an Enquiry_Code is already linked to another Lead, THE API SHALL still link it to this Lead and THE Admin_Panel SHALL show which other Lead used the same code.
11. WHEN a Lead with source `whatsapp` or `whatsapp_ad` is linked to an Enquiry_Code, THE API SHALL use the code's Channel instead of the manual Channel rule in Requirement 4.7.
12. THE Admin_Panel SHALL show on the Lead detail page the linked Enquiry_Code and the attribution it brought.
13. THE dashboard SHALL show the share of WhatsApp leads that carry an Enquiry_Code.
14. THE Customer_Site SHALL send no phone number, name or chat content to the API when registering an Enquiry_Code.

### Requirement 19: Required test cases

**User Story:** As a developer, I want explicit tests for lead capture, booking links and access control, so that regressions are caught.

#### Acceptance Criteria

1. THE API tests SHALL run on real PostgreSQL.
2. THE test suite SHALL test that Step 1 lead capture creates one Lead with source `website` and returns a Lead_Token, and that a second call with the token updates the same Lead.
3. THE test suite SHALL test that an invalid phone returns `422` and creates no Lead, and that client-supplied status, assignment and notes are ignored.
4. THE test suite SHALL test that submitting a booking with a Lead_Token links the booking, sets `booked`, and writes a `booking_linked` activity.
5. THE test suite SHALL test that a booking submitted without a Lead_Token creates a linked `booked` Lead.
6. THE test suite SHALL test that a lead-linking failure does not fail booking creation.
7. THE test suite SHALL test that accepting a linked booking sets `won`; rejecting, cancelling or expiring sets `follow_up`; reinstating sets `booked`.
8. THE test suite SHALL test that a booking created in admin without a lead creates no Lead, and that converting a lead links the booking.
9. THE test suite SHALL test the duplicate rule: an Open_Lead for the same phone and branch is reused; a Closed_Lead leads to a new Lead; concurrent creates yield one Open_Lead.
10. THE test suite SHALL test that closing a Lead without a Close_Reason returns `422`, that closing clears `follow_up_at`, and that manual `booked`/`won` is rejected.
11. THE test suite SHALL test that adding a call or WhatsApp activity on a `new` Lead sets `contacted` and `first_contacted_at`, and that activities cannot be edited or deleted.
12. THE test suite SHALL test access control: `401` without session, staff `403` for another branch's Lead, staff `200` for their own branch, staff `403` on the dashboard, admin `200` everywhere, and assignment to a user without branch access returns `422`.
13. THE test suite SHALL test the Auto_Close_Job: stale leads close with `no_response`, `booked` leads and leads with a future follow-up stay open, a second run changes nothing, and with `LEAD_AUTO_CLOSE_DAYS=0` nothing is closed.
14. THE test suite SHALL test the contact form and homepage form create Leads, the honeypot stores nothing, and `POST /api/v1/public/leads` returns `429` over the rate limit.
15. THE test suite SHALL test the `contact_leads` data migration copies rows into `leads` with source `contact_form`.
16. THE test suite SHALL test that no log output from lead endpoints contains the phone number or name.
17. THE Customer_Site Vitest suite SHALL test that Step 1 Next sends the lead without blocking navigation, that a failed lead request does not block the wizard, that the Lead_Token is reused, and that the booking request includes the Lead_Token.
18. THE Admin_Panel Vitest suite SHALL test quick-add phone normalisation, Overdue/Due_Today ordering, the follow-up WhatsApp message (format, 3,500-character cap, disabled states), and that Lead dashboard navigation is hidden from staff.
19. THE test suite SHALL test the Channel rules with one case per Channel, including fbclid, gclid, `utm_source=google&utm_medium=gbp`, a Google referrer, an Instagram referrer, an unknown referrer, no attribution, and manual sources (`whatsapp_ad` → `meta_ads`, `phone` → `manual`).
20. THE Customer_Site Vitest suite SHALL test the Landing_Store: landing on the homepage with UTM tags and then opening `/book` keeps the UTM tags; a later visit without campaign parameters keeps the stored attribution; a later visit with new campaign parameters replaces it; attribution older than 30 days is ignored; the stored landing path and referrer contain no query string; storage-unavailable does not throw.
21. THE test suite SHALL test Enquiry_Codes: registration stores attribution and Channel and no personal data; re-registration keeps the original attribution; an invalid format returns `422`; the endpoint returns `429` over the rate limit; quick-add with a valid code copies attribution and Channel onto a WhatsApp Lead; an unknown or expired code saves the Lead with a warning; a code already used by another Lead links with a notice.
22. THE test suite SHALL test the Uncontacted_New_Lead rule: a `new` Lead older than the threshold with no contact is counted; it stops counting after the first call or WhatsApp activity.
23. THE Customer_Site Vitest suite SHALL test that the WhatsApp links carry "Enquiry code: <code>", that the same code is reused, that WhatsApp opens even when registration fails, and that the registration body contains no phone or name.
24. THE change SHALL NOT be considered complete until `ruff`, `pytest`, `eslint`, and `vitest` pass.

