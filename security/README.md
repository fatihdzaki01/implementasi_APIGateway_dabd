## Security Module - Orang 4

**Authentication, Authorization, dan Rate Limiting untuk API Gateway**

### 📦 Modul ini menyediakan:

1. **Authentication** (JWT & API Key)
2. **Authorization** (Role-Based Access Control)
3. **Rate Limiting** (Sliding Window Algorithm)
4. **Auth Endpoints** (/auth/login, /auth/register, dll)

---

## 📂 Struktur File

```
security/
├── __init__.py           # Package initialization
├── config.py             # Configuration management (NEW)
├── auth.py               # Core authentication & authorization logic
├── middleware.py         # Middleware untuk gateway (auth + rate limit)
├── rate_limiter.py       # Rate limiting implementation
├── dependencies.py       # FastAPI dependencies (get_current_user, etc.)
├── router.py             # Auth endpoints (/auth/*)
├── init_roles.py         # Database role initialization script (NEW)
├── create_test_users.py  # Test user creation script (NEW)
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template (NEW)
└── README.md             # Dokumentasi ini
```

---

## 🔌 Integrasi dengan Gateway

### 1. Register Middleware di Gateway

Edit `gateway/main.py`:

```python
from gateway.middleware.pipeline import register_middleware
from security.middleware import auth_middleware, rate_limit_middleware

# Register middleware saat startup
@app.on_event("startup")
async def startup():
    # Rate limiting dulu (supaya rate limit di-check sebelum auth)
    register_middleware(rate_limit_middleware)
    # Lalu authentication & authorization
    register_middleware(auth_middleware)
```

### 2. Include Auth Router

```python
from security.router import router as auth_router

app.include_router(auth_router)
```

---

## 📋 Database Models

Modul ini menggunakan models dari `shared/models.py`:

### Table: `users`
- id (PK)
- username (unique)
- password_hash (bcrypt)
- role_id (FK → roles.id)
- is_active
- created_at

### Table: `roles`
- id (PK)
- name (unique) - e.g. "admin", "user", "readonly"
- permissions (JSON) - e.g. {"GET /service-a/*": true}
- created_at

### Table: `api_keys`
- id (PK)
- key_hash (hashed API key)
- user_id (FK → users.id)
- description
- is_active
- expires_at
- created_at

---

## 🚀 Cara Pakai

### 1. Setup Environment Variables

Copy `.env.example` ke `.env` dan update values:

```bash
cp security/.env.example security/.env
# Edit security/.env dengan text editor
```

**PENTING:** Ganti `JWT_SECRET_KEY` di production!

```bash
# Generate secure JWT secret key:
openssl rand -hex 32
```

### 2. Setup Database

Pastikan database sudah di-initialize dengan migration script dari `shared/migrations/`.

### 3. Create Default Roles

```bash
# Run dari root directory
python -m security.init_roles
```

Output:
```
✓ Created role 'admin'
✓ Created role 'user'
✓ Created role 'readonly'
✓ Created role 'service'

Role initialization complete!
```

### 4. Create Test Users (Optional - Development Only)

```bash
python -m security.create_test_users
```

⚠️ **WARNING:** Jangan run di production! Test users memiliki password weak.

### 5. Register User (via API)

### 5. Register User (via API)

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepass123",
    "role_name": "user"
  }'
```

### 6. Login

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepass123",
    "role_name": "user"
  }'
```

### 4. Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepass123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 5. Access Protected Endpoint

```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/service-a/items
```

---

## 🔐 Authentication Methods

### Method 1: JWT Token (Recommended)

```bash
# Login dulu untuk dapat token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"pass"}' | jq -r '.access_token')

# Pakai token di header
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/service-a/data
```

### Method 2: API Key

```bash
# Generate API key (harus authenticated dulu)
API_KEY=$(curl -s -X POST http://localhost:8000/auth/api-key \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description":"My API Key","expires_in_days":30}' | jq -r '.api_key')

# Pakai API key di header
curl -H "X-API-Key: $API_KEY" http://localhost:8000/service-a/data
```

---

## 🛡️ Authorization (RBAC)

### Format Permissions (JSON)

```json
{
  "GET /service-a/*": true,
  "POST /service-a/items": true,
  "DELETE /service-a/items/*": false,
  "* /admin/*": false
}
```

### Wildcard Patterns:

- `*` = semua methods
- `/*` = semua paths di bawah prefix
- Exact match lebih prioritas dari wildcard

### Example Roles:

**Admin:**
```json
{
  "* *": true
}
```

**User:**
```json
{
  "GET /service-a/*": true,
  "GET /service-b/*": true,
  "POST /service-a/items": true
}
```

**Readonly:**
```json
{
  "GET *": true
}
```

---

## ⚡ Rate Limiting

### Default Configuration:

- **Limit:** 100 requests
- **Window:** 60 seconds (1 minute)
- **Identifier:** User ID (jika authenticated) atau IP address

### Response Headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1726401720
```

### Rate Limit Exceeded (429):

```json
{
  "success": false,
  "data": null,
  "error": "Rate limit exceeded. Please try again later.",
  "request_id": "uuid-v4"
}
```

Headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1726401720
Retry-After: 60
```

### Custom Rate Limits:

Edit `security/rate_limiter.py`:

```python
# Init rate limiter dengan custom config
rate_limiter = RateLimiter(
    max_requests=200,    # 200 requests
    window_seconds=120   # per 2 minutes
)
```

### Production: Redis-based Rate Limiter

Untuk production dengan multiple gateway instances:

```python
from security.rate_limiter import RedisRateLimiter

rate_limiter = RedisRateLimiter(
    redis_host="redis",
    redis_port=6379,
    max_requests=100,
    window_seconds=60
)
```

---

## 🔧 FastAPI Dependencies

### Get Current User

```python
from security.dependencies import get_current_user

@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role.name}
```

### Require Specific Role

```python
from security.dependencies import require_role

@router.post("/admin/users")
async def create_user(user: User = Depends(require_role("admin"))):
    # Only admin can access
    pass
```

### Require Any of Multiple Roles

```python
from security.dependencies import require_any_role

@router.get("/data")
async def get_data(user: User = Depends(require_any_role("admin", "user"))):
    # Admin atau user bisa access
    pass
```

### Require Admin

```python
from security.dependencies import require_admin

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: User = Depends(require_admin)):
    # Only admin
    pass
```

---

## ⚙️ Configuration

### Environment Variables

Configuration dikelola via environment variables. See `.env.example` untuk template.

**Required:**
- `JWT_SECRET_KEY` - Secret key untuk JWT signing (WAJIB ganti di production!)

**Optional (dengan defaults):**
- `JWT_ALGORITHM` - Algorithm (default: HS256)
- `JWT_EXPIRATION_MINUTES` - Token expiry (default: 30)
- `RATE_LIMIT_MAX_REQUESTS` - Max requests (default: 100)
- `RATE_LIMIT_WINDOW_SECONDS` - Window (default: 60)

**Redis (Optional - untuk production):**
- `REDIS_HOST` - Redis hostname (default: localhost)
- `REDIS_PORT` - Redis port (default: 6379)
- `REDIS_DB` - Redis DB (default: 0)
- `USE_REDIS_RATE_LIMITER` - Enable Redis rate limiter (default: false)

### Loading Configuration

Configuration di-load otomatis dari environment variables saat module di-import:

```python
from security.config import config

print(config.JWT_SECRET_KEY)  # Access config values
print(config.RATE_LIMIT_MAX_REQUESTS)
```

### Docker Compose Integration

Tambahkan environment variables di `docker-compose.yml`:

```yaml
services:
  gateway:
    environment:
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - RATE_LIMIT_MAX_REQUESTS=200
      - USE_REDIS_RATE_LIMITER=true
```

---

## 🧪 Testing

### Test Auth Endpoints

```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"Test1234!","role_name":"user"}'

# 2. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"Test1234!"}'

# 3. Get current user info
TOKEN="<your-token-here>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me

# 4. Create API key
curl -X POST http://localhost:8000/auth/api-key \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description":"Test key","expires_in_days":30}'
```

### Test Middleware

```bash
# Test authentication required
curl http://localhost:8000/service-a/items
# Expected: 401 Unauthorized

# Test with valid token
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/service-a/items
# Expected: 200 OK (jika role memiliki permission)

# Test authorization failed
# Login sebagai readonly user, coba POST
curl -X POST -H "Authorization: Bearer $READONLY_TOKEN" \
  http://localhost:8000/service-a/items
# Expected: 403 Forbidden

# Test rate limiting
for i in {1..105}; do
  curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/service-a/items
done
# Expected: Request ke-101 akan return 429 Too Many Requests
```

---

## 📊 Response Format

Semua response mengikuti `shared.schemas.StandardResponse`:

### Success:
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "request_id": "uuid-v4"
}
```

### Error:
```json
{
  "success": false,
  "data": null,
  "error": "Error message here",
  "request_id": "uuid-v4"
}
```

---

## ⚠️ Security Best Practices

1. **JWT Secret Key:** Ganti `JWT_SECRET_KEY` di production! Simpan di environment variable.

2. **Password Policy:** Implement password validation (min length, complexity, dll).

3. **API Key Storage:** API key di-hash sebelum disimpan. Plain key hanya di-return 1x saat creation.

4. **HTTPS:** Gunakan HTTPS di production untuk protect token/API key di transit.

5. **Token Expiration:** Default 30 menit. Adjust sesuai kebutuhan.

6. **Rate Limit:** Adjust sesuai expected load. Monitor dan tune jika perlu.

---

## 🔄 Integration Flow

```
Request → Gateway
    ↓
Rate Limit Middleware (security/middleware.py)
    ↓ (check rate limit)
    ↓
Auth Middleware (security/middleware.py)
    ↓ (verify JWT/API key)
    ↓ (check role permission)
    ↓
Service Handler (gateway/router.py)
    ↓ (proxy ke backend service)
    ↓
Response → Client
```

---

## 📝 Kontrak Middleware

Sesuai `gateway/middleware/pipeline.py`:

```python
async def middleware_name(request: Request, call_next: Callable) -> Response:
    # Pre-processing
    # ...
    
    # Call next middleware/handler
    response = await call_next(request)
    
    # Post-processing
    # ...
    
    return response
```

---

## 🐛 Troubleshooting

### Issue: JWT token invalid

```bash
# Check token payload
python -c "
import jwt
token = 'your-token-here'
print(jwt.decode(token, options={'verify_signature': False}))
"
```

### Issue: Permission denied

Check role permissions di database:

```sql
SELECT r.name, r.permissions 
FROM roles r 
JOIN users u ON u.role_id = r.id 
WHERE u.username = 'testuser';
```

### Issue: Rate limit tidak berfungsi

- Check apakah `rate_limit_middleware` sudah di-register
- Check urutan middleware (rate limit sebelum auth)
- Check identifier (user_id atau IP)

---

## 📞 Maintainer

**Orang 4** - Security Module

Untuk pertanyaan atau issue, hubungi maintainer atau buat issue di repository.

---

## ✅ Checklist Integrasi

- [ ] Middleware registered di `gateway/main.py`
- [ ] Auth router included
- [ ] Database tables created (users, roles, api_keys)
- [ ] Default roles created
- [ ] Test user created
- [ ] JWT secret key di-set (production)
- [ ] Rate limit config di-adjust
- [ ] Documentation di-review

---

**Status: Ready for Integration** ✅
