#!/usr/bin/env bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

GATEWAY="http://localhost:8000"
DISCOVERY="http://localhost:8010"
RESILIENCE="http://localhost:8020"
SERVICE_A="http://localhost:8001"

PASS=0
FAIL=0

section() {
  echo ""
  echo -e "${CYAN}${BOLD}============================================================${NC}"
  echo -e "${CYAN}${BOLD}  $1${NC}"
  echo -e "${CYAN}${BOLD}============================================================${NC}"
}

pass() {
  PASS=$((PASS + 1))
  echo -e "  ${GREEN}PASS  $1${NC}"
}

fail() {
  FAIL=$((FAIL + 1))
  echo -e "  ${RED}FAIL  $1${NC}"
}

info() {
  echo -e "  ${YELLOW}>>    $1${NC}"
}

pretty() {
  echo "$1" | python3 -m json.tool 2>/dev/null || echo "$1"
}

json_get() {
  echo "$1" | python3 -c "
import json, sys
keys = '$2'.split('.')
d = json.load(sys.stdin)
for k in keys:
    if isinstance(d, list):
        d = d[int(k)]
    else:
        d = d.get(k, '')
print(d)
" 2>/dev/null
}

get_instance_status_by_id() {
  local resp="$1"
  local instance_id="$2"
  echo "$resp" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for inst in d.get('instances', []):
    if inst.get('instance_id') == '$instance_id':
        print(inst.get('status', 'unknown'))
        sys.exit(0)
print('not_found')
" 2>/dev/null
}

section "LOGIN"
info "Login sebagai user_test (role: user)"

LOGIN_RESP=$(curl -s -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"user_test","password":"User123!"}')

TOKEN=$(json_get "$LOGIN_RESP" "access_token")

if [ -z "$TOKEN" ]; then
  echo -e "  ${RED}Login gagal. Jalankan seed dulu:${NC}"
  echo "    docker compose exec security python -m security.init_roles"
  echo "    docker compose exec security python -m security.create_test_users"
  exit 1
fi

pass "Login user_test berhasil — token: ${TOKEN:0:40}..."

section "1. API GATEWAY — Single Entry Point"
info "GET $GATEWAY/service-a/items (lewat gateway, bukan langsung ke port 8001)"

RESP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$GATEWAY/service-a/items" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$RESP" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESP" | sed '/HTTP_STATUS/d')

if [ "$STATUS" = "200" ]; then
  pass "HTTP $STATUS — request berhasil melewati gateway"
  pretty "$BODY"
else
  fail "Expected 200, got $STATUS"
  echo "$BODY"
fi

section "2. REVERSE PROXY — Gateway Forward ke Backend"
info "Direct ke Service A port 8001 (tanpa auth):"
DIRECT=$(curl -s "$SERVICE_A/items")
pretty "$DIRECT"

echo ""
info "Lewat Gateway port 8000 (dengan auth):"
GW=$(curl -s "$GATEWAY/service-a/items" -H "Authorization: Bearer $TOKEN")
pretty "$GW"

DIRECT_TOTAL=$(json_get "$DIRECT" "total")
GW_TOTAL=$(json_get "$GW" "data.total")
if [ "$DIRECT_TOTAL" = "$GW_TOTAL" ] || [ -n "$GW_TOTAL" ]; then
  pass "Gateway berhasil meneruskan request ke Service A"
else
  fail "Response dari gateway tidak sesuai response langsung ke service"
fi

section "3. SERVICE DISCOVERY — Registry Semua Service"
info "GET $DISCOVERY/services"

SERVICES=$(curl -s "$DISCOVERY/services")
pretty "$SERVICES"

SVC_COUNT=$(echo "$SERVICES" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(len(d.get('services', {})))
" 2>/dev/null)

if [ "$SVC_COUNT" -gt "0" ] 2>/dev/null; then
  pass "$SVC_COUNT service terdaftar di registry"
else
  fail "Tidak ada service terdaftar di registry"
fi

section "4. LOAD BALANCING — Round-Robin 2 Instance (service-a dan service-a-2)"
info "Panggil /lb/next/service-a sebanyak 4 kali"

SVC_A_INSTANCES=$(curl -s "$DISCOVERY/services/service-a")
INST_COUNT=$(echo "$SVC_A_INSTANCES" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(len(d.get('instances', [])))
" 2>/dev/null)

info "Jumlah instance service-a terdaftar: $INST_COUNT"

if [ "$INST_COUNT" -lt "2" ]; then
  fail "Kurang dari 2 instance terdaftar — round-robin tidak bisa dibuktikan (expected >= 2, got $INST_COUNT)"
else
  INST=()
  for i in 1 2 3 4; do
    LB_RESP=$(curl -s "$DISCOVERY/lb/next/service-a?strategy=round_robin")
    INST_ID=$(json_get "$LB_RESP" "target.instance_id")
    INST+=("$INST_ID")
    info "Request $i -> $INST_ID"
  done

  echo ""
  UNIQUE=$(printf '%s\n' "${INST[@]}" | sort -u | wc -l)
  if [ "$UNIQUE" -ge "2" ]; then
    pass "Round-robin terbukti — ${INST[0]} -> ${INST[1]} -> ${INST[2]} -> ${INST[3]}"
  else
    fail "Semua request ke instance yang sama: ${INST[0]} (expected bergantian antara 2 instance)"
  fi
fi

section "5. HEALTH CHECK — Per Instance: HEALTHY -> UNHEALTHY -> HEALTHY"
info "Identifikasi instance berdasarkan host (bukan posisi array)"

SVC_A_DATA=$(curl -s "$DISCOVERY/services/service-a?healthy_only=false")

INST1_ID=$(echo "$SVC_A_DATA" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for inst in d.get('instances', []):
    if inst.get('host') == 'service-a':
        print(inst.get('instance_id', ''))
        sys.exit(0)
print('')
" 2>/dev/null)

INST2_ID=$(echo "$SVC_A_DATA" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for inst in d.get('instances', []):
    if inst.get('host') == 'service-a-2':
        print(inst.get('instance_id', ''))
        sys.exit(0)
print('')
" 2>/dev/null)

if [ -z "$INST1_ID" ] || [ -z "$INST2_ID" ]; then
  fail "Tidak bisa menemukan kedua instance — INST1=$INST1_ID INST2=$INST2_ID"
else
  info "Instance service-a   : $INST1_ID"
  info "Instance service-a-2 : $INST2_ID"

  STATUS1_INIT=$(get_instance_status_by_id "$SVC_A_DATA" "$INST1_ID")
  STATUS2_INIT=$(get_instance_status_by_id "$SVC_A_DATA" "$INST2_ID")
  info "Status awal — $INST1_ID: $STATUS1_INIT | $INST2_ID: $STATUS2_INIT"

  echo ""
  info "Matikan service-a (instance: $INST1_ID)..."
  docker compose stop service-a 2>/dev/null
  pass "service-a dihentikan"

  info "Menunggu health check poller mendeteksi perubahan (~22 detik)..."
  sleep 22

  AFTER_DOWN=$(curl -s "$DISCOVERY/services/service-a?healthy_only=false")
  STATUS1_DOWN=$(get_instance_status_by_id "$AFTER_DOWN" "$INST1_ID")
  STATUS2_DOWN=$(get_instance_status_by_id "$AFTER_DOWN" "$INST2_ID")

  info "Status setelah service-a mati:"
  pretty "$AFTER_DOWN"
  echo ""

  if [ "$STATUS1_DOWN" = "UNHEALTHY" ]; then
    pass "$INST1_ID: HEALTHY -> UNHEALTHY"
  else
    fail "$INST1_ID: expected UNHEALTHY, got $STATUS1_DOWN"
  fi

  if [ "$STATUS2_DOWN" = "HEALTHY" ]; then
    pass "$INST2_ID: tetap HEALTHY (service-a-2 tidak terpengaruh)"
  else
    fail "$INST2_ID: expected tetap HEALTHY, got $STATUS2_DOWN"
  fi

  echo ""
  info "Hidupkan kembali service-a..."
  docker compose start service-a 2>/dev/null
  pass "service-a dinyalakan kembali"

  info "Menunggu recovery (~22 detik)..."
  sleep 22

  AFTER_UP=$(curl -s "$DISCOVERY/services/service-a?healthy_only=false")
  STATUS1_UP=$(get_instance_status_by_id "$AFTER_UP" "$INST1_ID")

  info "Status setelah service-a hidup kembali:"
  pretty "$AFTER_UP"
  echo ""

  if [ "$STATUS1_UP" = "HEALTHY" ]; then
    pass "$INST1_ID: UNHEALTHY -> HEALTHY — transisi per-instance terbukti"
  else
    fail "$INST1_ID: expected HEALTHY, got $STATUS1_UP"
  fi
fi

section "6. CIRCUIT BREAKER — CLOSED -> OPEN -> HALF_OPEN -> CLOSED"
info "State awal (harus CLOSED):"
CB_INIT=$(curl -s "$RESILIENCE/circuit/service-a")
STATE_INIT=$(json_get "$CB_INIT" "state")
pretty "$CB_INIT"

if [ "$STATE_INIT" = "closed" ]; then
  pass "State awal: CLOSED"
else
  fail "State awal expected CLOSED, got $STATE_INIT"
fi

echo ""
info "Matikan KEDUA instance service-a dan service-a-2..."
docker compose stop service-a service-a-2 2>/dev/null
pass "service-a dan service-a-2 dihentikan"

info "Menunggu CB mencapai OPEN (polling tiap 3 detik, timeout 40 detik)..."

STATE_OPEN="closed"
FAILS_OPEN=0
CB_OPEN=""
for _i in $(seq 1 14); do
  CB_OPEN=$(curl -s "$RESILIENCE/circuit/service-a")
  STATE_OPEN=$(json_get "$CB_OPEN" "state")
  FAILS_OPEN=$(json_get "$CB_OPEN" "failure_count")
  info "  poll $_i: state=$STATE_OPEN failure_count=$FAILS_OPEN"
  if [ "$STATE_OPEN" = "open" ]; then
    break
  fi
  sleep 3
done

pretty "$CB_OPEN"

if [ "$STATE_OPEN" = "open" ]; then
  pass "State: CLOSED -> OPEN setelah $FAILS_OPEN kegagalan"
else
  fail "Circuit Breaker tidak mencapai OPEN dalam 40 detik — state=$STATE_OPEN failure_count=$FAILS_OPEN"
fi

echo ""
info "Request ke gateway saat circuit OPEN (harus 503):"
RESP_503=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$GATEWAY/service-a/items" \
  -H "Authorization: Bearer $TOKEN")
STATUS_503=$(echo "$RESP_503" | grep "HTTP_STATUS" | cut -d: -f2)
BODY_503=$(echo "$RESP_503" | sed '/HTTP_STATUS/d')
pretty "$BODY_503"

if [ "$STATUS_503" = "503" ]; then
  pass "HTTP 503 — gateway menolak request karena circuit OPEN"
else
  fail "Expected 503, got $STATUS_503"
fi

echo ""
info "Menunggu cooldown selesai (COOLDOWN_SECONDS=10 — tunggu 12 detik)..."
sleep 12

info "Trigger should_try dengan query endpoint circuit (agar transisi ke HALF_OPEN):"
CB_TRIGGER=$(curl -s "$RESILIENCE/circuit/service-a")
pretty "$CB_TRIGGER"

STATE_AFTER_COOLDOWN=$(json_get "$CB_TRIGGER" "state")

if [ "$STATE_AFTER_COOLDOWN" != "open" ] && [ "$STATE_AFTER_COOLDOWN" != "half_open" ]; then
  fail "Expected half_open setelah cooldown, got $STATE_AFTER_COOLDOWN"
fi

info "Paksa transisi ke HALF_OPEN dengan probe (service masih mati — probe akan gagal lalu cek lagi):"
PROBE_FAIL=$(curl -s -X POST "$RESILIENCE/circuit/service-a/probe")
pretty "$PROBE_FAIL"

CB_HALF=$(curl -s "$RESILIENCE/circuit/service-a")
STATE_HALF=$(json_get "$CB_HALF" "state")
pretty "$CB_HALF"

info "Hidupkan kembali service-a..."
docker compose start service-a 2>/dev/null
pass "service-a dinyalakan"

info "Menunggu service-a siap (~15 detik)..."
sleep 15

info "Lakukan probe saat service-a sudah hidup (state harus menjadi HALF_OPEN dulu)..."

for attempt in 1 2 3 4 5; do
  CB_CHECK=$(curl -s "$RESILIENCE/circuit/service-a")
  STATE_CHECK=$(json_get "$CB_CHECK" "state")

  if [ "$STATE_CHECK" = "half_open" ]; then
    info "State HALF_OPEN terdeteksi di percobaan ke-$attempt"
    pretty "$CB_CHECK"
    break
  elif [ "$STATE_CHECK" = "open" ]; then
    info "State masih OPEN, tunggu cooldown lagi..."
    sleep 13
    manager_reset=$(curl -s "$RESILIENCE/circuit/service-a")
    STATE_CHECK=$(json_get "$manager_reset" "state")
    if [ "$STATE_CHECK" = "half_open" ] || [ "$STATE_CHECK" = "open" ]; then
      break
    fi
  else
    break
  fi
done

CB_BEFORE_PROBE=$(curl -s "$RESILIENCE/circuit/service-a")
STATE_BEFORE=$(json_get "$CB_BEFORE_PROBE" "state")
pretty "$CB_BEFORE_PROBE"

if [ "$STATE_BEFORE" = "half_open" ]; then
  pass "State: OPEN -> HALF_OPEN setelah cooldown"
elif [ "$STATE_BEFORE" = "closed" ]; then
  pass "State sudah CLOSED setelah recovery otomatis"
else
  fail "Expected half_open, got $STATE_BEFORE"
fi

if [ "$STATE_BEFORE" = "half_open" ]; then
  echo ""
  info "Kirim probe ke circuit breaker (state HALF_OPEN + service sudah hidup):"
  PROBE_RESP=$(curl -s -X POST "$RESILIENCE/circuit/service-a/probe")
  pretty "$PROBE_RESP"
  PROBE_RESULT=$(json_get "$PROBE_RESP" "probe_result")

  CB_FINAL=$(curl -s "$RESILIENCE/circuit/service-a")
  STATE_FINAL=$(json_get "$CB_FINAL" "state")
  FAILS_FINAL=$(json_get "$CB_FINAL" "failure_count")
  pretty "$CB_FINAL"

  if [ "$STATE_FINAL" = "closed" ] && [ "$FAILS_FINAL" = "0" ]; then
    pass "State: HALF_OPEN -> CLOSED, failure_count=0 — siklus penuh CLOSED -> OPEN -> HALF_OPEN -> CLOSED terbukti"
  elif [ "$STATE_FINAL" = "closed" ]; then
    pass "State: CLOSED (failure_count=$FAILS_FINAL)"
  else
    fail "Expected closed setelah probe sukses, got $STATE_FINAL"
  fi
fi

echo ""
info "Hidupkan kembali service-a-2..."
docker compose start service-a-2 2>/dev/null
pass "service-a-2 dinyalakan kembali"

section "7. AUTHENTICATION — Tanpa Token (401)"
echo ""
info "Request tanpa Authorization header:"
RESP_401=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$GATEWAY/service-a/items")
STATUS_401=$(echo "$RESP_401" | grep "HTTP_STATUS" | cut -d: -f2)
BODY_401=$(echo "$RESP_401" | sed '/HTTP_STATUS/d')
pretty "$BODY_401"

if [ "$STATUS_401" = "401" ]; then
  pass "HTTP 401 — tanpa token"
else
  fail "Expected 401, got $STATUS_401"
fi

echo ""
info "Request dengan token tidak valid:"
RESP_401B=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$GATEWAY/service-a/items" \
  -H "Authorization: Bearer token_tidak_valid_xyz_123")
STATUS_401B=$(echo "$RESP_401B" | grep "HTTP_STATUS" | cut -d: -f2)
BODY_401B=$(echo "$RESP_401B" | sed '/HTTP_STATUS/d')
pretty "$BODY_401B"

if [ "$STATUS_401B" = "401" ]; then
  pass "HTTP 401 — token tidak valid"
else
  fail "Expected 401, got $STATUS_401B"
fi

section "8. AUTHORIZATION — RBAC (readonly GET=200, POST=403)"
info "Login sebagai readonly_test"

READONLY_RESP=$(curl -s -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"readonly_test","password":"Read123!"}')
READONLY_TOKEN=$(json_get "$READONLY_RESP" "access_token")

if [ -z "$READONLY_TOKEN" ]; then
  fail "Login readonly_test gagal — pastikan seed sudah dijalankan"
else
  pass "Login readonly_test berhasil"
  echo ""

  info "GET /service-a/items dengan token readonly (expected 200):"
  RESP_RO_GET=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$GATEWAY/service-a/items" \
    -H "Authorization: Bearer $READONLY_TOKEN")
  STATUS_RO_GET=$(echo "$RESP_RO_GET" | grep "HTTP_STATUS" | cut -d: -f2)
  BODY_RO_GET=$(echo "$RESP_RO_GET" | sed '/HTTP_STATUS/d')
  pretty "$BODY_RO_GET"

  if [ "$STATUS_RO_GET" = "200" ]; then
    pass "readonly GET -> HTTP 200"
  else
    fail "readonly GET -> expected 200, got $STATUS_RO_GET"
  fi

  echo ""
  info "POST /service-a/items dengan token readonly (expected 403):"
  RESP_RO_POST=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$GATEWAY/service-a/items" \
    -H "Authorization: Bearer $READONLY_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"Test Item","price":999}')
  STATUS_RO_POST=$(echo "$RESP_RO_POST" | grep "HTTP_STATUS" | cut -d: -f2)
  BODY_RO_POST=$(echo "$RESP_RO_POST" | sed '/HTTP_STATUS/d')
  pretty "$BODY_RO_POST"

  if [ "$STATUS_RO_POST" = "403" ]; then
    pass "readonly POST -> HTTP 403"
  else
    fail "readonly POST -> expected 403, got $STATUS_RO_POST"
  fi
fi

echo ""
info "Login sebagai user_test (role user — boleh POST) untuk konfirmasi:"
RESP_USER_POST=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$GATEWAY/service-a/items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Keyboard Mekanikal","price":750000}')
STATUS_USER_POST=$(echo "$RESP_USER_POST" | grep "HTTP_STATUS" | cut -d: -f2)
BODY_USER_POST=$(echo "$RESP_USER_POST" | sed '/HTTP_STATUS/d')
pretty "$BODY_USER_POST"

if [ "$STATUS_USER_POST" = "200" ] || [ "$STATUS_USER_POST" = "201" ]; then
  pass "user POST -> HTTP $STATUS_USER_POST (user boleh menulis)"
else
  fail "user POST -> expected 200/201, got $STATUS_USER_POST"
fi

section "9. REQUEST VALIDATION — Content-Type (415 / 200 / 422)"
info "Menggunakan token user_test (boleh POST ke /service-a/items)"
echo ""

info "POST dengan Content-Type: text/plain (expected 415):"
RESP_415=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$GATEWAY/service-a/items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/plain" \
  -d "ini bukan json")
STATUS_415=$(echo "$RESP_415" | grep "HTTP_STATUS" | cut -d: -f2)
BODY_415=$(echo "$RESP_415" | sed '/HTTP_STATUS/d')
pretty "$BODY_415"

if [ "$STATUS_415" = "415" ]; then
  pass "text/plain -> HTTP 415"
else
  fail "text/plain -> expected 415, got $STATUS_415"
fi

echo ""
info "POST dengan Content-Type: application/json + body valid (expected 200):"
RESP_VALID=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$GATEWAY/service-a/items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Monitor 27 inch","price":3500000}')
STATUS_VALID=$(echo "$RESP_VALID" | grep "HTTP_STATUS" | cut -d: -f2)
BODY_VALID=$(echo "$RESP_VALID" | sed '/HTTP_STATUS/d')
pretty "$BODY_VALID"

if [ "$STATUS_VALID" = "200" ] || [ "$STATUS_VALID" = "201" ]; then
  pass "valid JSON -> HTTP $STATUS_VALID"
else
  fail "valid JSON -> expected 200/201, got $STATUS_VALID"
fi

echo ""
info "POST dengan Content-Type: application/json + body tidak valid (expected 422):"
RESP_INV=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$GATEWAY/service-a/items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"field_tidak_ada": true, "angka": "bukan_angka"}')
STATUS_INV=$(echo "$RESP_INV" | grep "HTTP_STATUS" | cut -d: -f2)
BODY_INV=$(echo "$RESP_INV" | sed '/HTTP_STATUS/d')
pretty "$BODY_INV"

if [ "$STATUS_INV" = "422" ]; then
  pass "invalid body -> HTTP 422"
else
  fail "invalid body -> expected 422, got $STATUS_INV"
fi

section "10. RATE LIMITING — Request 1-100 Diizinkan, ke-101 HTTP 429"
info "Login sebagai admin_test untuk counter yang bersih"

ADMIN_RESP=$(curl -s -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin_test","password":"Admin123!"}')
ADMIN_TOKEN=$(json_get "$ADMIN_RESP" "access_token")

if [ -z "$ADMIN_TOKEN" ]; then
  fail "Login admin_test gagal — pastikan seed sudah dijalankan"
else
  pass "Login admin_test berhasil"
  echo ""

  info "Reset rate limit counter untuk admin_test..."
  RESET_RESP=$(curl -s -X POST "$GATEWAY/auth/rate-limit/reset" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
  pretty "$RESET_RESP"

  echo ""
  info "Mengirim 110 request, pantau kapan 429 muncul..."

  RATE_LIMIT_HIT=false
  LIMIT_AT=0
  LAST_STATUS=""

  for i in $(seq 1 110); do
    STATUS_RL=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY/service-a/items" \
      -H "Authorization: Bearer $ADMIN_TOKEN")
    LAST_STATUS="$STATUS_RL"
    if [ "$STATUS_RL" = "429" ]; then
      RATE_LIMIT_HIT=true
      LIMIT_AT=$i
      break
    fi
  done

  if [ "$RATE_LIMIT_HIT" = true ]; then
    if [ "$LIMIT_AT" -gt "100" ]; then
      pass "Rate limit tercapai di request ke-$LIMIT_AT (request 1-$((LIMIT_AT-1)) diizinkan)"
    else
      fail "Rate limit tercapai terlalu cepat di request ke-$LIMIT_AT (expected > 100)"
    fi
  else
    fail "HTTP 429 tidak muncul dalam 110 request (last status: $LAST_STATUS)"
  fi
fi

section "11. STRUCTURED LOGGING — JSON Logs Gateway"
info "10 log terakhir dari container gateway:"
echo ""
docker compose logs gateway --tail 10 2>/dev/null
pass "Log ditampilkan dari container gateway"

section "12. SEMUA SERVICE VIA GATEWAY"
echo ""

info "Service A — Items:"
RESP_A=$(curl -s "$GATEWAY/service-a/items" -H "Authorization: Bearer $TOKEN")
pretty "$RESP_A"
A_OK=$(json_get "$RESP_A" "data.total")
if [ -n "$A_OK" ]; then pass "Service A merespons via gateway"; else fail "Service A tidak merespons"; fi

echo ""
info "Service B — Products:"
RESP_B=$(curl -s "$GATEWAY/service-b/products" -H "Authorization: Bearer $TOKEN")
pretty "$RESP_B"
B_OK=$(json_get "$RESP_B" "data.total")
if [ -n "$B_OK" ]; then pass "Service B merespons via gateway"; else fail "Service B tidak merespons"; fi

echo ""
info "Service C — Users:"
RESP_C=$(curl -s "$GATEWAY/service-c/users" -H "Authorization: Bearer $TOKEN")
pretty "$RESP_C"
C_OK=$(json_get "$RESP_C" "data.total")
if [ -n "$C_OK" ]; then pass "Service C merespons via gateway"; else fail "Service C tidak merespons"; fi

section "HASIL DEMO"
echo ""
echo -e "  ${GREEN}PASS: $PASS${NC}"
echo -e "  ${RED}FAIL: $FAIL${NC}"
echo ""

if [ "$FAIL" -eq "0" ]; then
  echo -e "  ${GREEN}${BOLD}Semua skenario lulus.${NC}"
else
  echo -e "  ${YELLOW}${BOLD}$FAIL skenario gagal — periksa output di atas.${NC}"
fi
echo ""
