# Cinematic Celebration — Customer Site (`apps/web`)

Astro **static** customer site with React islands for the booking flow. The
site is a set of static HTML shells; all catalog, price, availability, and
booking data is fetched at **runtime** from the FastAPI backend (not at build
time), so catalog and price changes take effect without a site rebuild.

## Stack

- Astro 4 (static output) + `@astrojs/react` islands
- Tailwind CSS (`@astrojs/tailwind`)
- TypeScript (strict, extends `astro/tsconfigs/strict`)
- Vitest + Testing Library (jsdom) for unit/island tests

Keep the booking-page JS small (target **< 150 KB gzipped**): native `fetch`,
native `Intl` for money/dates, React state only — no date libraries, no global
store libraries.

## Environment

Astro exposes only `PUBLIC_`-prefixed variables to the browser. The booking
islands run client-side, so the API base URL must be public:

```
PUBLIC_API_BASE_URL=http://localhost:8000
```

Copy `.env.example` to `.env` and adjust per environment. The variable is read
at runtime in the browser bundle via `import.meta.env.PUBLIC_API_BASE_URL`
(default `http://localhost:8000`).

## Commands (Node LTS machine)

```bash
npm install        # install dependencies
npm run dev        # astro dev server (local development)
npm run build      # static build to dist/
npm run preview    # preview the built site
npm run test       # vitest run (unit + island smoke tests)
```

### Caveats

- The `dist/` build is static and can be hosted on Cloudflare Pages. No Node
  server runs in production.
- Islands call the API in the browser; set `PUBLIC_API_BASE_URL` to the
  deployed API origin for staging/production builds, and ensure that origin is
  in the API's CORS allowlist.
- `npm install` is required before `build`/`test`; this repo does not vendor
  `node_modules`. Until install runs, editors will report unresolved
  `astro`/`react` imports — expected.

## Static vs dynamic routing (important architecture decision)

The design sketch shows `[location]/index.astro` and `[location]/book.astro`
slug routes. With **static output** Astro must know every path at build time
(`getStaticPaths`), but **location slugs live in the database and are fetched at
runtime** — we deliberately do not fetch catalog data at build time. A dynamic
`[location]` path segment would therefore require SSR/`getStaticPaths`, which
conflicts with the static-build + no-Node-in-production constraint.

**Decision:** use static pages with **query parameters** and client-side
fetching instead of dynamic path segments:

| Page                     | Route                          | Island (fetch at runtime)        |
| ------------------------ | ------------------------------ | -------------------------------- |
| Landing                  | `/`                            | — (static copy)                  |
| Branch listing           | `/locations`                   | `LocationList`                   |
| Booking wizard           | `/book?location=<slug>`        | `BookingWizard` (`?plan=` opt.)  |
| Booking status lookup    | `/booking-status?token=<tok>`  | `BookingStatus`                  |
| Contact                  | `/contact`                     | `ContactForm`                    |

`/locations` links each branch to `/book?location=<slug>`. The wizard reads the
slug from `window.location.search`, resolves it via `GET /public/locations`,
then loads that location's catalog. This keeps the whole site static while
still being fully data-driven at runtime.

## Structure

```
src/
├── pages/              # index, locations, book, booking-status, contact (static shells)
├── layouts/Base.astro  # HTML shell: SEO (title/meta/OG), JSON-LD slot, robots allow
├── components/booking/ # React islands: BookingWizard, SlotPicker, AddonSelector,
│                       #   BookingForm, BookingStatus, LocationList, ContactForm
├── lib/                # api.ts (typed public client), formatters.ts (Intl money/date)
├── styles/global.css   # Tailwind entry
└── test/setup.ts       # jest-dom matchers
public/robots.txt       # allow all (the customer site is indexable; admin is noindex)
```

## SEO

Every page sets a unique `<title>`, meta description, and Open Graph tags via
`Base.astro`. The landing and locations pages include `LocalBusiness` JSON-LD
for local search. `robots.txt` allows all crawlers — the customer site is the
indexable surface; the admin panel is the `noindex` one.
```
