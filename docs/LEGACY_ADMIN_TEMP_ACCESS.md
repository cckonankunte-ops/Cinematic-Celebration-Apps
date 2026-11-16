# Legacy Admin — Temporary Access Setup

Operational note. After migrating production to Cloudflare / DigitalOcean /
Postgres, we temporarily re-enabled the **old Hostinger admin app + old MySQL
database** so historical data can be verified before the Hostinger VPS is
retired. This is a throwaway setup — see Rollback / Cleanup at the end.

> **Critical:** keep a final `mysqldump` export of the old MySQL database before
> canceling the Hostinger VPS. Do not cancel until that backup is verified.

## Objective

Temporary access to the old admin UI + old MySQL to verify legacy data before
shutting down Hostinger.

- Temporary URL: `https://oldadmin.cinematiccelebration.in`
- The temporary legacy stack uses the **old Hostinger MySQL** DB — NOT the new
  DigitalOcean Postgres.

## Architecture (temporary legacy)

```
oldadmin.cinematiccelebration.in
        │  HTTPS :443
        ▼
Hostinger OpenLiteSpeed
   ├── Old Admin UI (static files)
   └── /api/*  → reverse proxy → 127.0.0.1:8082
                                   │
                                   ▼
                        Old Node/Express API
                                   │
                                   ▼
                        MySQL localhost:3306 (OLD DB)
```

New production remains independent and untouched:

```
cinematiccelebration.in         → Cloudflare Pages
www.cinematiccelebration.in     → Cloudflare Pages
admin.cinematiccelebration.in   → Cloudflare Pages
api.cinematiccelebration.in     → DigitalOcean (Postgres)
```

## What was done

### 1. Cloudflare DNS

Temporary record (DNS-only, not proxied):

```
Type: A
Name: oldadmin
Value: 82.29.167.116   (Hostinger VPS)
Proxy status: DNS only
TTL: Auto
```

So `oldadmin.cinematiccelebration.in → 82.29.167.116`. The production records
above are unaffected.

### 2. CyberPanel temporary subdomain

Created `oldadmin.cinematiccelebration.in` under the old
`admin.cinematiccelebration.in` site, PHP 8.3. CyberPanel's actual vHost docRoot
is:

```
/home/admin.cinematiccelebration.in/oldadmin.cinematiccelebration.in/
```

(An initial copy to `/home/admin.cinematiccelebration.in/public_html/subdomain`
did NOT work — that is not the vHost docRoot.) The old admin static files were
copied into the correct docRoot: `index.html`, `.htaccess`, `favicon.ico`,
`css/`, `img/`, `js/`.

### 3. SSL

Issued a Let's Encrypt cert via CyberPanel for
`oldadmin.cinematiccelebration.in`, so the UI serves over normal HTTPS.

### 4. Old API identified

The compiled old admin frontend originally called
`https://cinematiccelebration.in:8081/api/`. Port 8081 on the Hostinger VPS still
runs the old Node app at `/home/cinematiccelebration.in/public_html/app.js`,
managed by PM2 (`name: app`, `id: 0`). Verified with
`POST /api/user/login/` → `{"error":"Invalid credentials"}` for empty creds.

### 5. Old database confirmed

Old Node `.env`: `MYSQL_HOST=localhost`, `MYSQL_PORT=3306`, plus user/password/
database; `package.json` uses `mysql ^2.18.1`. The temporary old admin keeps
using the Hostinger MySQL DB (not the new Postgres).

### 6. Internal HTTP listener added to the old Node API

`app.js` exposed the API only over HTTPS on `*:8081`, which caused
`ERR_CERT_COMMON_NAME_INVALID` when the browser hit
`https://oldadmin.cinematiccelebration.in:8081`. Backed up `app.js` →
`app.js.before_oldadmin_proxy`, then added a localhost-only HTTP listener:

```js
const http = require("http");
http.createServer(app).listen(8082, "127.0.0.1", () => {
  console.log("Legacy internal HTTP API running on http://127.0.0.1:8082");
});
```

The original HTTPS :8081 listener was left untouched. After `pm2 restart app`,
both `*:8081` and `127.0.0.1:8082` are served by the same app. 8082 binds to
`127.0.0.1` only, so it is not publicly exposed.

### 7. OpenLiteSpeed reverse proxy

In OLS WebAdmin (`https://82.29.167.116:7080`), for vHost
`oldadmin.cinematiccelebration.in`:

- Web Server External App: `Name: legacy-api`, `Address: 127.0.0.1:8082`,
  `Max Connections: 100`, `Initial Timeout: 60`, `Retry Timeout: 0`,
  `Response Buffering: No`.
- Proxy Context: `URI: /api/` → Web Server `legacy-api`.
- Graceful restart.

Verified: `POST https://oldadmin.cinematiccelebration.in/api/user/login/` →
`HTTP/2 401`, `server: LiteSpeed`, `x-powered-by: Express`,
`{"error":"Invalid credentials"}` (401 expected — no valid creds; confirms the
full proxy chain works).

### 8. Temporary admin frontend API URL

Changed the copied frontend's API base from
`https://cinematiccelebration.in:8081/api/` → ... →
`https://oldadmin.cinematiccelebration.in/api/` (final). The final version does
not use port 8081 from the browser.

## Rollback / Cleanup (after verification)

Reverse order, once all legacy data has been checked:

1. Remove the `oldadmin` DNS record from Cloudflare.
2. Remove `oldadmin.cinematiccelebration.in` from CyberPanel.
3. Remove the `legacy-api` External App and the `/api/` Proxy Context from
   OpenLiteSpeed.
4. Remove the temporary HTTP :8082 listener from `app.js`, or restore the backup:
   ```sh
   cp app.js.before_oldadmin_proxy app.js
   pm2 restart app
   ```
5. Verify 8082 is gone:
   ```sh
   ss -lntp | grep 8082
   ```
6. **Back up / export the old MySQL database and verify the dump**, then the old
   Hostinger Node/API/MySQL stack and ultimately the Hostinger VPS can be retired.

> Reminder: do NOT cancel the Hostinger VPS until a verified final MySQL backup
> exists. (The new system's migration was from a MariaDB dump — see
> `PRODUCTION_CUTOVER.md` / `scripts/migrate_from_mariadb`.)
