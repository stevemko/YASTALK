#!/bin/bash
cd /workspaces/YASTALK
BASE=http://localhost:8000/api
TS=$(date +%s)
EMAIL="test$TS@example.com"
PASS="Strong-pass-2026"
J='Content-Type: application/json'

check()  { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; fi; }
status() { curl -s -o /dev/null -w "%{http_code}" "$@"; }
field()  { python3 -c "import sys,json; print(json.load(sys.stdin).get('$1',''))"; }
REG="{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"first_name\":\"Test\"}"

echo "--- basic endpoints"
check "health"                 200 $(status $BASE/health/)
check "health (HEAD request)"  200 $(status -I $BASE/health/)
check "app-links"              200 $(status $BASE/app-links/)
check "events list"            200 $(status $BASE/events/)
check "services list"          200 $(status $BASE/services/)

echo "--- accounts"
check "register"                   201 $(status -X POST $BASE/auth/register/ -H "$J" -d "$REG")
check "duplicate email rejected"   400 $(status -X POST $BASE/auth/register/ -H "$J" -d "$REG")
check "weak password rejected"     400 $(status -X POST $BASE/auth/register/ -H "$J" -d "{\"email\":\"weak$TS@example.com\",\"password\":\"12345678\",\"first_name\":\"W\"}")

LOGIN=$(curl -s -X POST $BASE/auth/login/ -H "$J" -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")
ACCESS=$(echo "$LOGIN" | field access); REFRESH=$(echo "$LOGIN" | field refresh)
check "login returns tokens"       yes $([ -n "$ACCESS" ] && [ -n "$REFRESH" ] && echo yes || echo no)
check "/me with token"             200 $(status $BASE/auth/me/ -H "Authorization: Bearer $ACCESS")
check "/me without token"          401 $(status $BASE/auth/me/)

NEW=$(curl -s -X POST $BASE/auth/refresh/ -H "$J" -d "{\"refresh\":\"$REFRESH\"}")
ACCESS2=$(echo "$NEW" | field access); REFRESH2=$(echo "$NEW" | field refresh)
check "refresh gives new tokens"   yes $([ -n "$ACCESS2" ] && [ -n "$REFRESH2" ] && echo yes || echo no)
check "old refresh token revoked"  401 $(status -X POST $BASE/auth/refresh/ -H "$J" -d "{\"refresh\":\"$REFRESH\"}")
check "logout"                     204 $(status -X POST $BASE/auth/logout/ -H "Authorization: Bearer $ACCESS2" -H "$J" -d "{\"refresh\":\"$REFRESH2\"}")
check "refresh after logout"       401 $(status -X POST $BASE/auth/refresh/ -H "$J" -d "{\"refresh\":\"$REFRESH2\"}")

echo "--- lockout (5 failures, then blocked)"
BAD="{\"email\":\"lock$TS@example.com\",\"password\":\"wrong-password\"}"
for i in 1 2 3 4 5; do status -X POST $BASE/auth/login/ -H "$J" -d "$BAD" > /dev/null; done
check "6th attempt locked"         429 $(status -X POST $BASE/auth/login/ -H "$J" -d "$BAD")

echo "--- payments"
check "bad phone rejected"         400 $(status -X POST $BASE/payments/initiate/ -H "$J" -d '{"plan":"mini","phone":"12345","email":"b@example.com"}')
check "unknown plan rejected"      400 $(status -X POST $BASE/payments/initiate/ -H "$J" -d '{"plan":"nope","phone":"0712345678","email":"b@example.com"}')

SECRET=$(grep '^MPESA_CALLBACK_SECRET=' .env | cut -d= -f2-)
PAY_ID=$(python manage.py shell -c "
from core.models import Payment
p = Payment.objects.create(email='sim@example.com', phone='254712345678', plan='mini', amount=499, checkout_request_id='ws_CO_TEST_$TS')
print(p.id)
" | tail -1)
CB="{\"Body\":{\"stkCallback\":{\"MerchantRequestID\":\"x\",\"CheckoutRequestID\":\"ws_CO_TEST_$TS\",\"ResultCode\":0,\"ResultDesc\":\"ok\",\"CallbackMetadata\":{\"Item\":[{\"Name\":\"Amount\",\"Value\":499},{\"Name\":\"MpesaReceiptNumber\",\"Value\":\"TEST$TS\"},{\"Name\":\"PhoneNumber\",\"Value\":254712345678}]}}}}"
check "callback, wrong secret"     404 $(status -X POST $BASE/payments/mpesa/callback/not-the-secret/ -H "$J" -d '{}')
check "callback, right secret"     200 $(status -X POST "$BASE/payments/mpesa/callback/$SECRET/" -H "$J" -d "$CB")
check "payment marked success"     success "$(curl -s $BASE/payments/$PAY_ID/status/ | field status)"

echo "--- CORS"
OK=$(curl -s -i -X OPTIONS $BASE/auth/login/ -H "Origin: https://yas-talk.vercel.app" -H "Access-Control-Request-Method: POST" | grep -ci "access-control-allow-origin")
BADO=$(curl -s -i -X OPTIONS $BASE/auth/login/ -H "Origin: https://evil.example.com" -H "Access-Control-Request-Method: POST" | grep -ci "access-control-allow-origin")
check "CORS allows your Vercel site" 1 "$OK"
check "CORS blocks unknown site"     0 "$BADO"
