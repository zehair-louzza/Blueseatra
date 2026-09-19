#!/usr/bin/env sh
# Validate .env.preprod before starting anything.
# Refuses placeholder values and production-looking secrets/hosts.
set -eu

cd "$(dirname "$0")/.."

if [ ! -f .env.preprod ]; then
  echo "Missing .env.preprod. Copy .env.preprod.example and fill it first." >&2
  exit 1
fi

fail=0

# --- Production-looking values are refused ---------------------------------
refuse_pattern() {
  # refuse_pattern <label> <extended regex>
  if grep -Eq "$2" .env.preprod; then
    echo "REFUSED: $1 detected in .env.preprod." >&2
    fail=1
  fi
}

refuse_pattern "Supabase production host (supabase.co)"     "supabase[.]co"
refuse_pattern "Supabase service-role secret (sb_secret_)"  "sb_secret_"
refuse_pattern "Stripe live secret key (sk_live_)"           "sk_live_"
refuse_pattern "Stripe live webhook secret (whsec_)"         "whsec_"
refuse_pattern "production Hermes gateway (hermes.blueseatra.com)" "hermes[.]blueseatra[.]com"

# --- Mandatory variables must be set to real values -------------------------
require_set() {
  # require_set <variable> [min_length]
  var="$1"
  min="${2:-1}"
  val=$(grep -E "^${var}=" .env.preprod | head -n 1 | cut -d= -f2-)
  if [ -z "$val" ] || printf '%s' "$val" | grep -q "replace-with"; then
    echo "MISSING: $var is empty or still a placeholder in .env.preprod." >&2
    fail=1
  elif [ "${#val}" -lt "$min" ]; then
    echo "TOO SHORT: $var must be at least $min characters." >&2
    fail=1
  fi
}

require_set POSTGRES_PASSWORD        24
require_set PREPROD_APP_DB_PASSWORD  24
require_set REDIS_PASSWORD           24
require_set MINIO_ROOT_PASSWORD      24
require_set JWT_SECRET               48
require_set APP_ENCRYPTION_KEY        48
require_set HERMES_BASE_URL          12

if [ "$fail" -ne 0 ]; then
  echo "" >&2
  echo "Validation FAILED — fix the issues above, then re-run." >&2
  exit 1
fi

echo "OK: .env.preprod passed preproduction validation."
