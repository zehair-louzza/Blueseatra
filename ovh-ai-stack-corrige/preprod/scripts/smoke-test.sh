#!/usr/bin/env sh
# End-to-end smoke test for the Blueseatra preprod stack.
# Prerequisite: ./scripts/bootstrap.sh && ./scripts/migrate.sh --apply
# and the app profile started: docker compose --env-file .env.preprod --profile app up -d
#
#   ./scripts/smoke-test.sh    exits 0 on a healthy preprod, non-zero with a clear message otherwise

set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env.preprod ]; then
  echo "Missing .env.preprod. Run bootstrap.sh first." >&2
  exit 1
fi

. ./.env.preprod 2>/dev/null || true

API_URL="${SMOKE_API_URL:-http://localhost:8000}"
DB_USER="${POSTGRES_USER:-blueseatra_preprod}"
DB_NAME="${POSTGRES_DB:-blueseatra_preprod}"
STAMP=$(date +%s)
TEST_EMAIL="smoke-test+${STAMP}@blueseatra.invalid"
TEST_PASSWORD="Smoke-Test-$(openssl rand -hex 8)"
TEST_NAME="Smoke Test ${STAMP}"

fail() {
  echo "SMOKE TEST FAILED: $1" >&2
  cleanup
  exit 1
}

cleanup() {
  docker compose --env-file .env.preprod exec -T postgres \
    psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=0 -c \
    "DELETE FROM blueseatra.requests WHERE tenant_id IN (SELECT tenant_id FROM blueseatra.tenant_users tu JOIN blueseatra.users u ON u.id = tu.user_id WHERE u.email = '${TEST_EMAIL}'); \
     DELETE FROM blueseatra.tenant_users WHERE user_id IN (SELECT id FROM blueseatra.users WHERE email = '${TEST_EMAIL}'); \
     DELETE FROM blueseatra.tenants WHERE id NOT IN (SELECT DISTINCT tenant_id FROM blueseatra.tenant_users) AND name = '${TEST_NAME}'; \
     DELETE FROM blueseatra.users WHERE email = '${TEST_EMAIL}';" \
    >/dev/null 2>&1 || true
}

echo "==> 1/5 Waiting for API health"
for i in $(seq 1 30); do
  if curl -fsS "${API_URL}/api/health" >/dev/null 2>&1; then
    break
  fi
  [ "$i" -eq 30 ] && fail "API did not become healthy at ${API_URL}/api/health"
  sleep 2
done

echo "==> 2/5 Signup test user"
SIGNUP_BODY=$(curl -fsS -X POST "${API_URL}/api/auth/signup" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\",\"name\":\"${TEST_NAME}\"}") \
  || fail "signup request failed"

echo "==> 3/5 Login"
LOGIN_BODY=$(curl -fsS -X POST "${API_URL}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}") \
  || fail "login request failed"
TOKEN=$(printf '%s' "$LOGIN_BODY" | grep -o '"token"[^,}]*' | head -n1 | sed -E 's/.*:\s*"([^"]+)".*/\1/')
[ -n "$TOKEN" ] || TOKEN=$(printf '%s' "$LOGIN_BODY" | grep -o '"access_token"[^,}]*' | head -n1 | sed -E 's/.*:\s*"([^"]+)".*/\1/')
[ -n "$TOKEN" ] || fail "could not extract auth token from login response: $LOGIN_BODY"

echo "==> 4/5 Create a minimal request (queues an extraction job on Redis/RQ)"
REQ_BODY=$(curl -fsS -X POST "${API_URL}/api/requests" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Smoke test request: 1 unite de test, aucune donnee reelle."}') \
  || fail "request creation failed"
REQUEST_ID=$(printf '%s' "$REQ_BODY" | grep -o '"id"[^,}]*' | head -n1 | sed -E 's/.*:\s*"?([a-zA-Z0-9-]+)"?.*/\1/')
[ -n "$REQUEST_ID" ] || fail "could not extract request id from response: $REQ_BODY"

echo "==> 5/5 Waiting for the worker to consume the queued job (request ${REQUEST_ID})"
for i in $(seq 1 30); do
  STATUS_BODY=$(curl -fsS "${API_URL}/api/requests/${REQUEST_ID}" -H "Authorization: Bearer ${TOKEN}") \
    || fail "could not poll request status"
  STATUS=$(printf '%s' "$STATUS_BODY" | grep -o '"status"[^,}]*' | head -n1 | sed -E 's/.*:\s*"([^"]+)".*/\1/')
  if [ "$STATUS" != "queued" ] && [ -n "$STATUS" ]; then
    echo "Worker processed the job — status is now: ${STATUS}"
    break
  fi
  [ "$i" -eq 30 ] && fail "worker never consumed the queued job (still 'queued' after 60s)"
  sleep 2
done

cleanup
echo "SMOKE TEST PASSED"
exit 0
