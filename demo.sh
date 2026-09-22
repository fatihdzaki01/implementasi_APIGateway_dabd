#!/usr/bin/env bash
# =============================================================
# demo.sh — Demo Script Presentasi API Gateway & Microservices
# Jalankan: bash demo.sh
# Pastikan docker compose sudah up sebelum menjalankan script ini
# =============================================================

# --- Warna terminal ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# --- URL ---
GATEWAY="http://localhost:8000"
DISCOVERY="http://localhost:8010"
RESILIENCE="http://localhost:8020"
SERVICE_A="http://localhost:8001"

# --- Helper ---
section() {
  echo ""
  echo -e "${CYAN}${BOLD}============================================================${NC}"
  echo -e "${CYAN}${BOLD}  $1${NC}"
  echo -e "${CYAN}${BOLD}============================================================${NC}"
}

ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
info() { echo -e "  ${YELLOW}→ $1${NC}"; }
fail() { echo -e "  ${RED}✗ $1${NC}"; }

pretty() {
  # pretty-print JSON atau tampilkan raw jika bukan JSON
  echo "$1" | python3 -m json.tool 2>/dev/null || echo "$1"
}

# =============================================================
# LOGIN — ambil token untuk semua request berikutnya
# =============================================================
section "LOGIN — Ambil JWT Token"
info "POST $GATEWAY/auth/login (username: user_test)"

LOGIN_RESP=$(curl -s -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"user_test","password":"User123!"}')

TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  fail "Login gagal! Pastikan user_test sudah terdaftar."
  info "Coba register dulu:"
  info "curl -s -X POST $GATEWAY/auth/register -H 'Content-Type: application/json' -d '{\"username\":\"user_test\",\"password\":\"User123!\",\"role_name\":\"user\"}'"
  exit 1
fi

ok "Login berhasil! Token: ${TOKEN:0:40}..."

# =============================================================
# 1. API GATEWAY — satu pintu masuk
# =============================================================
section "1. API GATEWAY — Single Entry Point"
info "Request dikirim ke Gateway (port 8000), bukan langsung ke Service A (port 8001)"
info "GET $GATEWAY/service-a/items"

RESP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$GATEWAY/service-a/items" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$RESP" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESP" | sed '/HTTP_STATUS/d')

if [ "$STATUS" = "200" ]; then
  ok "Response dari Gateway — HTTP $STATUS"
  pretty "$BODY"
else
  fail "Gagal — HTTP $STATUS"
  echo "$BODY"
fi

# =============================================================
# 2. REVERSE PROXY — gateway teruskan ke backend
# =============================================================
section "2. REVERSE PROXY — Gateway Forward ke Backend"
info "Buktikan: request ke Gateway → diteruskan → Service A merespons"
info ""
info "Direct ke Service A (port 8001) — tanpa auth:"
DIRECT=$(curl -s "$SERVICE_A/items")
pretty "$DIRECT"

info ""
info "Lewat Gateway (port 8000) — dengan auth middleware:"
GW=$(curl -s "$GATEWAY/service-a/items" -H "Authorization: Bearer $TOKEN")
pretty "$GW"

ok "Kedua response sama → Gateway berhasil forward request ke Service A"

# =============================================================
# 3. SERVICE DISCOVERY — registry semua service
# =============================================================
section "3. SERVICE DISCOVERY — Registry Semua Service"
info "GET $DISCOVERY/services"

SERVICES=$(curl -s "$DISCOVERY/services")
ok "Daftar service yang terdaftar:"
pretty "$SERVICES"

# =============================================================
# 4. LOAD BALANCING — round-robin pilih instance
# =============================================================
section "4. LOAD BALANCING — Round-Robin Instance Selection"
info "GET $DISCOVERY/lb/next/service-a (panggil 3x untuk lihat round-robin)"

for i in 1 2 3; do
  info "Request ke-$i:"
  LB=$(curl -s "$DISCOVERY/lb/next/service-a?strategy=round_robin")
  pretty "$LB"
  echo ""
done

ok "Setiap request → load balancer pilih instance berikutnya (round-robin)"

# =============================================================
# 5. HEALTH CHECK — status kesehatan tiap service
# =============================================================
section "5. HEALTH CHECK — Status Kesehatan Service"

for SERVICE in "gateway:8000:/health" "discovery-lb:8010:/" "resilience:8020:/health" "service-a:8001:/health" "service-b:8002:/health" "service-c:8003:/health"; do
  NAME=$(echo $SERVICE | cut -d: -f1)
  PORT=$(echo $SERVICE | cut -d: -f2)
  ENDPOINT=$(echo $SERVICE | cut -d: -f3)
  HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT$ENDPOINT")
  if [ "$HEALTH" = "200" ]; then
    ok "$NAME (port $PORT) → HEALTHY ✅"
  else
    fail "$NAME (port $PORT) → HTTP $HEALTH ❌"
  fi
done

info ""
info "Detail instance sehat di registry:"
HEALTHY=$(curl -s "$DISCOVERY/services?healthy_only=true" 2>/dev/null || curl -s "$DISCOVERY/services")
pretty "$HEALTHY"

# =============================================================
# 6. CIRCUIT BREAKER — state per service
# =============================================================
section "6. CIRCUIT BREAKER — State Per Service"
info "GET $RESILIENCE/status — semua circuit breaker aktif"

CB_STATUS=$(curl -s "$RESILIENCE/status")
pretty "$CB_STATUS"

echo ""
for SVC in service-a service-b service-c; do
  info "Circuit breaker $SVC:"
  CB=$(curl -s "$RESILIENCE/circuit/$SVC")
  STATE=$(echo "$CB" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state','unknown'))" 2>/dev/null)
  FAILS=$(echo "$CB" | python3 -c "import json,sys; print(json.load(sys.stdin).get('failure_count',0))" 2>/dev/null)
  if [ "$STATE" = "closed" ]; then
    ok "$SVC → state: $STATE | failures: $FAILS (normal, semua sehat)"
  elif [ "$STATE" = "open" ]; then
    fail "$SVC → state: $STATE | failures: $FAILS (circuit OPEN — service dianggap down)"
  else
    echo -e "  ${YELLOW}⚠ $SVC → state: $STATE | failures: $FAILS${NC}"
  fi
done

# =============================================================
# SUMMARY
# =============================================================
section "SUMMARY — Semua Konsep Berhasil Didemonstrasikan"
echo ""
echo -e "  ${GREEN}1. API Gateway      → Single entry point port 8000${NC}"
echo -e "  ${GREEN}2. Reverse Proxy    → Gateway forward ke backend service${NC}"
echo -e "  ${GREEN}3. Service Discovery→ Registry otomatis di port 8010${NC}"
echo -e "  ${GREEN}4. Load Balancing   → Round-robin pilih instance${NC}"
echo -e "  ${GREEN}5. Health Check     → Monitor status tiap service${NC}"
echo -e "  ${GREEN}6. Circuit Breaker  → Proteksi jika service down${NC}"
echo ""
echo -e "${BOLD}  Sistem dibangun dengan FastAPI + Docker Compose${NC}"
echo ""
