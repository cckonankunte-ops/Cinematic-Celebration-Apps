#!/usr/bin/env bash
# Wire the frontend + backend .env files to the correct URLs.
#
# In GitHub Codespaces, forwarded ports are reachable at:
#   https://$CODESPACE_NAME-<port>.$GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN
# This script fills those real URLs into:
#   - apps/admin/.env   (VITE_API_BASE_URL -> API @ 8000)
#   - apps/web/.env      (PUBLIC_API_BASE_URL -> API @ 8000)
#   - apps/api/.env      (CORS_ALLOWED_ORIGINS -> admin @ 5173 + web @ 4321)
#
# Run it inside the Codespace AFTER setup, any time (idempotent):
#   bash .devcontainer/wire-env.sh
#
# Outside Codespaces it falls back to localhost URLs.
set -e

if [ -n "$CODESPACE_NAME" ] && [ -n "$GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN" ]; then
  BASE="https://${CODESPACE_NAME}"
  DOMAIN="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
  API_URL="${BASE}-8000.${DOMAIN}"
  ADMIN_URL="${BASE}-5173.${DOMAIN}"
  WEB_URL="${BASE}-4321.${DOMAIN}"
else
  API_URL="http://localhost:8000"
  ADMIN_URL="http://localhost:5173"
  WEB_URL="http://localhost:4321"
fi

echo "API_URL   = $API_URL"
echo "ADMIN_URL = $ADMIN_URL"
echo "WEB_URL   = $WEB_URL"

# --- admin/.env ---
mkdir -p apps/admin
cat > apps/admin/.env <<EOF
VITE_API_BASE_URL=${API_URL}
EOF

# --- web/.env ---
mkdir -p apps/web
cat > apps/web/.env <<EOF
PUBLIC_API_BASE_URL=${API_URL}
EOF

# --- api/.env: update CORS + cookie policy (preserve DATABASE_URL etc.) ---
API_ENV="apps/api/.env"
[ -f "$API_ENV" ] || cp apps/api/.env.example "$API_ENV"
ORIGINS="${ADMIN_URL},${WEB_URL}"

# set_kv KEY VALUE — replace the KEY=... line in-place, or append if missing.
set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$API_ENV"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$API_ENV"
  else
    echo "${key}=${val}" >> "$API_ENV"
  fi
}

set_kv CORS_ALLOWED_ORIGINS "$ORIGINS"

if [ -n "$CODESPACE_NAME" ]; then
  # Cross-subdomain over HTTPS -> cookie must be SameSite=None; Secure.
  set_kv ENVIRONMENT "staging"
  set_kv COOKIE_SAMESITE "none"
  set_kv COOKIE_SECURE "true"
else
  set_kv ENVIRONMENT "local"
  set_kv COOKIE_SAMESITE "lax"
  set_kv COOKIE_SECURE "false"
fi

echo ""
echo "Wired:"
echo "  apps/admin/.env  VITE_API_BASE_URL=${API_URL}"
echo "  apps/web/.env     PUBLIC_API_BASE_URL=${API_URL}"
echo "  apps/api/.env     CORS_ALLOWED_ORIGINS=${ORIGINS}"
if [ -n "$CODESPACE_NAME" ]; then
  echo "  apps/api/.env     COOKIE_SAMESITE=none, COOKIE_SECURE=true (Codespaces)"
fi
echo ""
echo "Reminder: set DATABASE_URL in apps/api/.env to your Neon string,"
echo "and make the forwarded API port (8000) PUBLIC in the Ports tab."
