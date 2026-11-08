# Requirements — Offers Headline Banner (Feature, draft)

## Introduction

A scrolling headline/offers banner on the customer site (like the BingeTown
"LIMITED TIME OFFER: Use SHARK300 …" marquee), with an admin screen to create and
manage the headline/offer content. This is distinct from the minimal coupon
showcase in `customer-booking-flow-v2` (Requirement 11): this spec owns editable,
scheduled, free-form promotional content and its management UI.

This is a DRAFT requirements stub captured so the feature isn't lost. It should be
fleshed out (design + tasks) as its own spec after `customer-booking-flow-v2`.

## Requirements (draft)

### Requirement 1 — Admin-managed headline/offer content

**User Story:** As the owner, I want to add and edit promotional headlines/offers,
so that I can announce current deals on the site without a developer.

#### Acceptance Criteria (draft)

1. WHERE the admin is authenticated THEN the system SHALL let an admin create,
   edit, activate/deactivate, and delete headline items (text, optional link,
   optional start/end dates, sort order).
2. WHEN multiple headline items are active THEN the banner SHALL show them in the
   configured order (scrolling/rotating).
3. WHEN a headline has a schedule THEN it SHALL only display within its active
   date window.
4. WHEN content changes THEN the customer site SHALL reflect it via a public,
   cacheable endpoint (no redeploy).

### Requirement 2 — Customer scrolling banner

**User Story:** As a customer, I want to see current offers in a prominent banner,
so that I know about deals immediately.

#### Acceptance Criteria (draft)

1. WHEN the customer site loads THEN a scrolling/marquee banner SHALL display the
   active headline items at runtime.
2. WHEN there are no active items THEN the banner SHALL be hidden with no layout
   shift.
3. WHEN a headline has a link THEN tapping it SHALL navigate appropriately.
4. WHERE a headline references a coupon code THEN it SHALL be display-only; the
   discount is still validated/computed server-side at booking time.

## Scope notes (draft)

- Likely needs a new table `headline_offers` (text, link, start/end dates,
  is_active, sort_order), an admin CRUD under `/api/v1/admin/...`, and a public
  `GET /api/v1/public/headline-offers`.
- Mobile-first marquee; keep the web bundle small (no heavy carousel libs).
- Decide overlap with coupon offers: a headline may be free text OR reference an
  existing coupon; avoid duplicating coupon truth.
- Accessibility: scrolling content must be pausable / not trap focus; respect
  `prefers-reduced-motion`.

## Status

Draft stub. Promote to full requirements → design → tasks when scheduled (after
`customer-booking-flow-v2`).
