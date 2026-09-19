from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal


# ============================================================
# KONTRAK DATA — disepakati seluruh tim, JANGAN ubah tanpa diskusi
# ============================================================


class ServiceInstance(BaseModel):
    """
    Format entry di service registry.
    Dipakai oleh: discovery-lb, resilience, gateway/router.
    """
    service_name: str                                          # e.g. "service-a"
    host: str                                                  # e.g. "service-a" (docker hostname) atau "localhost"
    port: int                                                  # e.g. 8001
    status: Literal["healthy", "unhealthy", "unknown"] = "unknown"
    last_heartbeat: datetime
    weight: int = 1                                            # untuk weighted load balancing


class RequestLog(BaseModel):
    """
    Format structured log untuk setiap request yang masuk ke gateway.
    Dipakai oleh: shared/logging_config.py, gateway middleware, tabel request_logs di DB.
    """
    request_id: str                                            # UUID v4
    timestamp: datetime
    method: str                                                # GET | POST | PUT | DELETE | PATCH
    path: str                                                  # path asli dari client, e.g. /service-a/items
    target_service: Optional[str] = None                       # nama service tujuan, e.g. "service-a"
    status_code: int
    response_time_ms: float
    user_id: Optional[str] = None                             # None kalau request tidak terauthentikasi
    ip_address: str


class StandardResponse(BaseModel):
    """
    Format response standar yang keluar dari gateway ke client.
    Semua response HARUS menggunakan format ini.
    """
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    request_id: Optional[str] = None


# ============================================================
# Auth schemas
# ============================================================

class TokenPayload(BaseModel):
    """Payload yang di-encode di dalam JWT token."""
    user_id: str
    username: str
    role: str
    exp: int                                                   # Unix timestamp expiry


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int                                            # detik


# ============================================================
# Registry schemas
# ============================================================

class RegisterRequest(BaseModel):
    """Payload yang dikirim service saat mendaftarkan diri ke registry."""
    service_name: str
    host: str
    port: int
    weight: int = 1


class DeregisterRequest(BaseModel):
    service_name: str
    host: str
    port: int
