# Cinematic Celebration — Admin Panel

React 18 + TypeScript (strict) single-page app built with Vite. Used by staff
and owners to manage bookings, record advance payments, view operational
sheets, and track revenue. It is a static build (served from Cloudflare Pages)
and is `noindex`. API calls use cookies (`credentials: 'include'`).

## Prerequisites

- Node.js LTS (18+)
- The API running locally (default `http://localhost:8000`) for live data

## Setup

```bash
npm install
cp .env.example .env   # adjust VITE_API_BASE_URL if needed
```

## Generate API types

The TypeScript types in `src/api/schema.ts` are generated from the backend's
OpenAPI contract. First export the contract on the API side, then generate:

```bash
# in apps/api — produces apps/api/openapi.json
python scripts/export_openapi.py

# in apps/admin — reads ../api/openapi.json
npm run gen:api
```

## Common commands

```bash
npm run dev        # start the Vite dev server on http://localhost:5173
npm run build      # type-check (tsc -b) and build the static bundle to dist/
npm run preview    # preview the production build
npm run lint       # ESLint
npm test           # run the Vitest suite once
npm run test:watch # watch mode
```

## Configuration

| Variable            | Default                 | Description               |
| ------------------- | ----------------------- | ------------------------- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base URL of the API.      |

## Project layout

```
src/
├── api/        # generated schema.ts + thin fetch client (credentials: 'include')
├── features/   # auth/, bookings/, timesheet/, cakesheet/, analytics/, location/
├── hooks/      # useDebounce, ...
├── lib/        # money.ts, dates.ts (Asia/Kolkata), whatsapp.ts
├── routes/     # React Router route tree
└── main.tsx    # app entry (QueryClientProvider + RouterProvider)
```
