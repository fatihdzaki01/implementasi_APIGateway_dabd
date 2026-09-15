# Implementasi API Gateway & Microservices — DABD

Proyek implementasi API Gateway lengkap dengan microservices untuk tugas DABD.

## Fitur yang Diimplementasikan
1. API Gateway (reverse proxy, routing)
2. Service Discovery
3. Load Balancing (round robin)
4. Health Check
5. Circuit Breaker
6. Rate Limiter
7. Authentication (JWT)
8. Authorization (RBAC)
9. Request Validation
10. Logging Terstruktur

---

## Struktur Repo & Pembagian Tugas

```
repo/
├── gateway/          → Orang 1  : API Gateway core, reverse proxy, middleware pipeline
├── discovery-lb/     → Orang 2  : Service registry, load balancing
├── resilience/       → Orang 3  : Health check, circuit breaker
├── security/         → Orang 4  : Auth (JWT), authorization (RBAC), rate limiter
├── shared/           → Orang 5  : DB, logging, validation, integrasi end-to-end
├── services/         → Semua    : Dummy service A/B/C untuk testing
│   ├── service_a/
│   ├── service_b/
│   └── service_c/
└── docker-compose.yml
```

---

## Kontrak Antar-Modul (WAJIB DIPATUHI)

### Middleware Signature
Semua middleware **harus** mengikuti signature berikut (lihat `gateway/middleware/pipeline.py`):
```python
async def nama_middleware(request: Request, call_next: Callable) -> Response:
    # pre-processing
    response = await call_next(request)
    # post-processing
    return response
```

### Format Service Registry
Lihat `shared/schemas.py` → class `ServiceInstance`:
```python
{
  "service_name": "service-a",
  "host": "service-a",
  "port": 8001,
  "status": "healthy",          # "healthy" | "unhealthy" | "unknown"
  "last_heartbeat": "2024-01-01T00:00:00",
  "weight": 1
}
```

### Format Response Standar
Semua response dari gateway ke client **harus** pakai `StandardResponse`:
```python
{
  "success": true,
  "data": { ... },
  "error": null,
  "request_id": "uuid-v4"
}
```

---

## Setup & Cara Jalan

### 1. Clone repo & masuk branch masing-masing
```bash
git clone git@github.com:fatihdzaki01/implementasi_APIGateway_dabd.git
cd implementasi_APIGateway_dabd

# Checkout ke branch nama kamu
git checkout fatih   # atau raihan / gloria / yoeke / dhea
```

### 2. Init database (sekali saja)
```bash
# Via docker (otomatis saat docker compose up)
docker compose up db -d

# Atau manual
psql -U user -d gateway_db -f shared/migrations/init_db.sql
```

### 3. Jalankan semua service sekaligus
```bash
docker compose up --build
```

### 4. Port yang dipakai
| Service | Port |
|---|---|
| API Gateway | `8000` |
| Service A | `8001` |
| Service B | `8002` |
| Service C | `8003` |
| Discovery/LB | `8010` |
| PostgreSQL | `5432` |

### 5. Test cepat
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

---

## Workflow Git

- **Branch `main`** : kode final yang sudah bersih
- **Branch `dev`** : integrasi semua modul (dipimpin Orang 5)
- **Branch personal** (`fatih`, `raihan`, `gloria`, `yoeke`, `dhea`) : workspace masing-masing orang

```
main ← dev ← fatih
              raihan
              gloria
              yoeke
              dhea
```

Saat mau merge ke `dev`, buat **Pull Request** dan minta review minimal 1 orang.

---

## Dependencies Shared

File `shared/` **tidak boleh dimodifikasi sepihak**. Kalau ada perubahan schema/model/db, diskusi dulu dan buat PR ke branch `dev`.

| File | Fungsi |
|---|---|
| `shared/schemas.py` | Pydantic schemas — kontrak data lintas modul |
| `shared/db.py` | Koneksi DB + `get_db()` dependency |
| `shared/models.py` | ORM models (tabel DB) |
| `shared/logging_config.py` | Structured logger (JSON) |
| `shared/validation.py` | Request validation middleware |
| `shared/migrations/init_db.sql` | DDL script semua tabel |
