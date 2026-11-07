# Old Application — Tech Stack (legacy, live on Hostinger)

Analysis of the existing production system in `Old_Application/`. This is the
currently-live Cinematic Celebration website (customer site + admin + backend)
running on Hostinger. **Not modified** — documented here for reference and to
inform migration/deployment decisions.

Three apps + one DB dump:
- `backend/` — Node.js/Express API
- `admin/` — Vue 2 admin panel
- `frontend/` — Vue 2 customer site
- `cine_celebration.sql` — MySQL/MariaDB schema + data dump

---

## Backend (API) — `Old_Application/backend`

| Component | Technology | Version |
|---|---|---|
| Runtime | Node.js | — |
| Framework | Express.js | 4.18.2 |
| DB driver | `mysql` (callback-style) | 2.18.1 |
| Connection pool | `mysql.createPool`, `connectionLimit: 10` | — |
| Auth tokens | jsonwebtoken (JWT) | 8.5.1 |
| Password hashing | bcrypt **(installed but NOT used — passwords are plain text)** | 5.1.0 |
| Payments (primary) | phonepesdk-web | 1.0.7 |
| Payments (secondary) | razorpay (dependency present) | 2.8.4 |
| Email | nodemailer (Gmail SMTP) | 6.8.0 |
| HTTP client | axios | 1.2.0 |
| CORS | cors — **open to all origins** (`app.use(cors())`) | 2.8.5 |
| Config | dotenv | 16.0.3 |
| Hashing utils | sha256, base-64, crypto, utf-8, zlib | — |
| Dev tooling | nodemon | 2.0.20 |
| Server port | 8081 (env `PORT`) | — |
| TLS | Let's Encrypt — **HTTPS block commented out in `app.js`; runs HTTP** | — |
| Static files | Express static at `/gallery` for plan images | — |

**Backend layout:** `app.js` (entry) → `src/route/*` (contactus, booking, user,
analytics) → `src/controller/*` → `src/service/*` (incl. `service/phonepe/`).
Middleware `verifyToken.js` exists but is largely unused. DB config in
`config/database.js`.

**API route groups:** `/api/contact-us`, `/api/booking`, `/api/user`,
`/api/analytics`.

## Admin panel — `Old_Application/admin`

| Component | Technology | Version |
|---|---|---|
| Framework | Vue.js (Vue 2, Options API) | 2.6.14 |
| Build | Vue CLI (`@vue/cli-service`) | 5.0.0 |
| UI library | Vuetify (Material Design) | 2.6.12 |
| State | Vuex | 3.6.2 |
| Routing | Vue Router | 3.5.1 |
| HTTP | axios | 1.2.0 |
| JWT decode | jwt-decode | 4.0.0 |
| Dates | moment.js | 2.29.4 |
| Charts | chart.js + vue-chartjs, highcharts + highcharts-vue | 4.4.1 / 11.3.0 |
| Excel export | xlsx, vue-excel-export | 0.18.5 / 0.1.3 |
| PDF export | vue-html2pdf | 1.8.0 |
| Utilities | lodash, lodash.debounce | 4.17.21 |
| Toasts | vue-toastification | 1.7.14 |
| Auth storage | JWT in `localStorage` | — |

## Customer site — `Old_Application/frontend`

| Component | Technology | Version |
|---|---|---|
| Framework | Vue.js (Vue 2) | 2.6.14 |
| Build | Vue CLI | 5.0.0 |
| UI library | Vuetify | 2.6.12 |
| State | Vuex | 3.6.2 |
| Routing | Vue Router | 3.5.1 |
| HTTP | axios | 1.2.0 |
| Payments | phonepesdk-web **and** cashfree-elementjs | 1.0.7 / 1.1.8 |
| Analytics | Firebase (`firebase/app`, `firebase/analytics`) | 10.6.0 |
| Carousel | slick-carousel, vue-slick-carousel | — |
| Lazy images | v-lazy-image, v-lazy-load, vue-blurhash | — |
| Utilities | lodash, sha256, buffer | — |

> Note: `frontend/src/js/firebase.js` contains a **hardcoded Firebase config**
> (apiKey, project `happy-harbour`) committed in source. The project name
> "happy-harbour" is a legacy name predating "Cinematic Celebration".

## Database — `cine_celebration.sql`

| Component | Detail |
|---|---|
| Engine | MariaDB 10.11.x (MySQL-compatible) |
| Driver used | node `mysql` (callback) with a 10-connection pool |
| Tables | 11 — booking, cake, combos, contact_form_leads, location, occasion, plan, slot, special_decor, status, users, user_role |
| Storage engine | InnoDB |
| Foreign keys | **None** — relationships are implicit via ID columns |
| Charsets | **Mixed** — latin1, utf8mb3, utf8mb4 across tables |
| Money | Plain integer columns (no consistent paise convention) |
| JSON-in-text | `plan.galleryimages`, `booking.specialdecorselected`, `booking.combosselected` stored as text/longtext |
| Legacy decor flags | booking has boolean `tinyint` columns (tabledecor, foggyrosepetalpath, balloondecor, rosebouquet, photoprop, gloosyphoto) |

---

## Known technical debt (legacy)

- **Passwords stored in plain text** (bcrypt present but unused).
- **CORS open to all origins** — no allowlist.
- **HTTPS commented out** — the app serves HTTP; TLS depends on external setup.
- **Auth largely unenforced** — `verifyToken` middleware exists but is commented
  out on nearly all routes; only one route uses JWT. Most endpoints are public.
- **Hardcoded secrets** — JWT secret keys hardcoded in route files (and differ
  between `booking.js` and `user.js`); Firebase config hardcoded in frontend.
- **No foreign keys** and **mixed character sets** in the DB.
- **No input validation / rate limiting / request sanitisation.**
- **JWT in localStorage** (vulnerable to XSS token theft).
- Two payment SDKs partially wired (PhonePe + Cashfree/Razorpay) without a clean
  provider abstraction.

---

## How this maps to the New Application

| Concern | Old (legacy) | New (Phase 1) |
|---|---|---|
| Backend | Node/Express + `mysql` | Python/FastAPI + SQLAlchemy 2.0 (sync) + psycopg3 |
| DB | MariaDB, no FKs, mixed charset | PostgreSQL 16, real FKs, UTF-8, integer paise |
| Admin/customer | Vue 2 + Vuetify (Vue CLI) | React 18 + Vite (admin), Astro + React islands (web) |
| Auth | JWT in localStorage, plain-text passwords, open CORS | JWT in httpOnly+Secure cookie, argon2 hashing, explicit CORS allowlist, role checks |
| Payments | PhonePe + Cashfree, no abstraction | Manual advance (Phase 1); PhonePe later behind a `PaymentProvider` interface |
| Hosting | Hostinger, HTTP, direct Node process | VPS (Docker: API+Postgres+Caddy, auto-HTTPS) + Cloudflare Pages + R2 |
| Pricing | Mixed client/server | Server-authoritative (`services/pricing.py`) |

The legacy flaws above are the exact things the new system's steering rules were
written to avoid.
