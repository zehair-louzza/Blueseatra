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

set -a
. ./.env.preprod
set +a

API_URL="${SMOKE_API_URL:-http://127.0.0.1:8080}"
DB_USER="${POSTGRES_USER:-blueseatra_preprod}"
DB_NAME="${POSTGRES_DB:-blueseatra_preprod}"
STAMP=$(date +%s)
TEST_EMAIL="smoke-test+${STAMP}@example.com"
TEST_PASSWORD="Smoke-Test-$(openssl rand -hex 8)"
TEST_NAME="Smoke Test ${STAMP}"
TEST_TENANT_ID=""
TEST_USER_ID=""

cleanup() {
  [ -n "$TEST_TENANT_ID" ] || return 0
  docker compose --env-file .env.preprod exec -T postgres \
    psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
    -v tenant_id="$TEST_TENANT_ID" -v user_id="$TEST_USER_ID" <<'SQL' >/dev/null
-- audit_logs est en ajout seul : purge des traces de test par maintenance explicite.
BEGIN;
SET LOCAL blueseatra.maintenance_audit = 'on';
DELETE FROM blueseatra.audit_logs WHERE tenant_id = :'tenant_id';
COMMIT;
DELETE FROM blueseatra.quote_versions WHERE tenant_id = :'tenant_id';
DELETE FROM blueseatra.quotes WHERE tenant_id = :'tenant_id';
DELETE FROM blueseatra.requests WHERE tenant_id = :'tenant_id';
DELETE FROM blueseatra.import_errors WHERE tenant_id = :'tenant_id';
DELETE FROM blueseatra.import_jobs WHERE tenant_id = :'tenant_id';
DELETE FROM blueseatra.pricing_items WHERE tenant_id = :'tenant_id';
DELETE FROM blueseatra.catalog_versions WHERE tenant_id = :'tenant_id';
DELETE FROM blueseatra.catalogs WHERE tenant_id = :'tenant_id';
DELETE FROM blueseatra.tenant_users WHERE tenant_id = :'tenant_id' AND user_id = :'user_id';
DELETE FROM blueseatra.tenants WHERE id = :'tenant_id';
DELETE FROM blueseatra.users WHERE id = :'user_id';
SQL
}
trap cleanup EXIT

fail() {
  echo "SMOKE TEST FAILED: $1" >&2
  exit 1
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
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\",\"name\":\"${TEST_NAME}\",\"company\":\"${TEST_NAME}\"}") \
  || fail "signup request failed"
TEST_TENANT_ID=$(printf '%s' "$SIGNUP_BODY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["tenant"]["id"])') \
  || fail "signup response has no tenant id"
TEST_USER_ID=$(printf '%s' "$SIGNUP_BODY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["user"]["id"])') \
  || fail "signup response has no user id"

echo "==> 3/5 Login"
LOGIN_BODY=$(curl -fsS -X POST "${API_URL}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}") \
  || fail "login request failed"
TOKEN=$(printf '%s' "$LOGIN_BODY" | python3 -c 'import sys,json; obj=json.load(sys.stdin); print(obj.get("token") or obj.get("access_token") or "")') \
  || fail "invalid login response JSON"
[ -n "$TOKEN" ] || fail "could not extract auth token"

echo "==> 4/5 Create a minimal request (queues an extraction job on Redis/RQ)"
REQ_BODY=$(curl -fsS -X POST "${API_URL}/api/requests" \
  -H "Authorization: Bearer ${TOKEN}" \
  --form "title=Smoke test ${STAMP}" \
  --form 'text=Smoke test request: 1 unite de test, aucune donnee reelle.') \
  || fail "request creation failed"
REQUEST_ID=$(printf '%s' "$REQ_BODY" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])') \
  || fail "could not extract request id"

echo "==> 5/5 Waiting for the worker to consume the queued job (request ${REQUEST_ID})"
for i in $(seq 1 30); do
  STATUS_BODY=$(curl -fsS "${API_URL}/api/requests/${REQUEST_ID}" -H "Authorization: Bearer ${TOKEN}") \
    || fail "could not poll request status"
  STATUS=$(printf '%s' "$STATUS_BODY" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("status", ""))') \
    || fail "invalid request status JSON"
  if [ "$STATUS" = "done" ] || [ "$STATUS" = "needs_review" ] || [ "$STATUS" = "failed" ]; then
    echo "Worker processed the job — status is now: ${STATUS}"
    break
  fi
  [ "$i" -eq 30 ] && fail "worker never consumed the queued job (still 'queued' after 60s)"
  sleep 2
done

echo "SMOKE TEST PASSED"
exit 0
