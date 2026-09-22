"""
API Gateway — FastAPI app entrypoint.
Orang 1 (gateway) yang maintain file ini.

Semua request masuk lewat gateway ini, lalu di-forward ke service backend
lewat middleware pipeline + reverse proxy handler.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from gateway.config import ROUTING_TABLE
from gateway.middleware.pipeline import register_middleware, get_middlewares, run_pipeline
from gateway.router import reverse_proxy_handler, _get_client


logger = logging.getLogger("gateway.main")


# ============================================================
# Lifespan — startup & shutdown events
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    print("=" * 60)
    print("  API Gateway — Starting...")
    print("=" * 60)
    print(f"  DISCOVERY_URL  : {os.getenv('DISCOVERY_URL', 'http://localhost:8010')}")
    print(f"  RESILIENCE_URL : {os.getenv('RESILIENCE_URL', 'http://localhost:8020')}")
    print(f"  JWT_SECRET     : {'(set)' if os.getenv('JWT_SECRET') else '(default)'}")
    print(f"  DATABASE_URL   : {'(set)' if os.getenv('DATABASE_URL') else '(not set)'}")
    print()
    print("  Routing Table:")
    for prefix, config in ROUTING_TABLE.items():
        print(f"    {prefix:20s} → {config['service_name']}")
    print()
    print("  Registered Middlewares:")
    for mw in get_middlewares():
        print(f"    ✓ {mw.__module__}.{mw.__qualname__}")
    if not get_middlewares():
        print("    (none)")
    print("=" * 60)

    yield

    # --- SHUTDOWN ---
    client = await _get_client()
    if client and not client.is_closed:
        await client.aclose()
    print("API Gateway — Shutdown complete.")


# ============================================================
# FastAPI app
# ============================================================

app = FastAPI(
    title="API Gateway",
    description="API Gateway untuk Microservices — DABD",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — izinkan semua origin untuk development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Custom OpenAPI — inject securitySchemes supaya tombol
# Authorize 🔒 muncul di Swagger UI (/docs)
# ============================================================

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Inject BearerAuth scheme → ini yang bikin tombol Authorize muncul
    openapi_schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token dari POST /auth/login. Masukkan token-nya saja (tanpa kata 'Bearer').",
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# ============================================================
# Register middleware ke pipeline
# Urutan: logging → auth → rate_limit → validation
# (Sesuai kontrak di gateway/middleware/pipeline.py)
#
# Middleware dari modul lain di-import dengan try/except
# supaya gateway bisa jalan mandiri meskipun modul belum ready.
# ============================================================

def _register_all_middlewares():
    """Register semua middleware ke pipeline. Panggil saat startup."""
    # 1. Logging middleware (Orang 5 — shared)
    try:
        from shared.logging_config import logging_middleware
        register_middleware(logging_middleware)
        print("[gateway] ✓ logging_middleware registered")
    except (ImportError, AttributeError):
        print("[gateway] - logging_middleware not available (Orang 5 belum selesai)")

    # 2. Auth middleware (Orang 4 — security)
    try:
        from security.middleware import auth_middleware
        register_middleware(auth_middleware)
        print("[gateway] ✓ auth_middleware registered")
    except (ImportError, AttributeError) as e:
        print(f"[gateway] - auth_middleware not available: {e}")

    # 3. Rate limiter middleware (Orang 4 — security)
    try:
        from security.middleware import rate_limit_middleware
        register_middleware(rate_limit_middleware)
        print("[gateway] ✓ rate_limit_middleware registered")
    except (ImportError, AttributeError) as e:
        print(f"[gateway] - rate_limit_middleware not available: {e}")

    # 4. Validation middleware (Orang 5 — shared)
    try:
        from shared.validation import validation_middleware
        register_middleware(validation_middleware)
        print("[gateway] ✓ validation_middleware registered")
    except (ImportError, AttributeError):
        print("[gateway] - validation_middleware not available (Orang 5 belum selesai)")


_register_all_middlewares()


# ============================================================
# Routes
# ============================================================

@app.get("/health")
async def gateway_health():
    """
    Health check untuk gateway itu sendiri.
    Gateway selalu return healthy (ini cuma nge-check gateway hidup/tidak).
    """
    return {"status": "healthy", "service": "api-gateway"}


# ============================================================
# Auth routes — include langsung dari security module
# ============================================================
try:
    from security.router import router as auth_router
    app.include_router(auth_router)
    print("[gateway] ✓ Auth router included (/auth/*)")
except Exception as e:
    print(f"[gateway] - Auth router not available: {e}")


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False,
)
async def catch_all(request: Request):
    """
    Catch-all route — semua request yang tidak match route lain
    akan di-forward ke service backend lewat middleware pipeline.

    Early 404 check dilakukan sebelum masuk pipeline supaya path yang
    tidak terdaftar tidak melewati auth middleware (dan return 401).

    Pipeline flow:
        request → [route check] → logging → auth → rate_limit → validation → reverse_proxy → response
    """
    import uuid
    from gateway.config import get_route

    # Early route check — return 404 sebelum masuk pipeline
    route = get_route(request.url.path)
    if route is None:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": f"Tidak ada route untuk path: {request.url.path}",
                "request_id": str(uuid.uuid4()),
                "data": None,
            },
        )

    async def forwarder(req: Request):
        return await reverse_proxy_handler(req)

    try:
        return await run_pipeline(request, forwarder)
    except Exception as e:
        logger.error(f"Unhandled error in gateway: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Internal gateway error: {str(e)}",
                "request_id": None,
                "data": None,
            },
        )
