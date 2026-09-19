"""
Reverse proxy handler — core dari Orang 1.
Forward request dari client ke service backend lewat discovery service.

Kontrak ke Orang 2 (discovery-lb):
    GET {DISCOVERY_URL}/services/{service_name}/instances
    → [{"service_name": "...", "host": "...", "port": ..., "status": "healthy", ...}]

Kontrak ke Orang 3 (resilience):
    GET {RESILIENCE_URL}/circuit/{service_name}
    → {"state": "closed"|"open"|"half-open"}
"""

import uuid
import httpx
import os
from fastapi import Request
from fastapi.responses import JSONResponse

from gateway.config import get_route

DISCOVERY_URL = os.getenv("DISCOVERY_URL", "http://localhost:8010")
RESILIENCE_URL = os.getenv("RESILIENCE_URL", "http://localhost:8020")

# HTTP client — timeout singkat supaya gateway ga hang nunggu service mati
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    return _client


async def _get_healthy_instances(service_name: str) -> list[dict]:
    """
    Fetch instance healthy dari discovery service.
    Return list of instance dicts, kosong jika discovery down / service tidak ada.
    """
    try:
        client = await _get_client()
        resp = await client.get(
            f"{DISCOVERY_URL}/services/{service_name}"
        )
        if resp.status_code == 200:
            data = resp.json()
            instances = data.get("instances", data) if isinstance(data, dict) else data
            if isinstance(instances, list):
                return [i for i in instances if i.get("status", "").lower() == "healthy"]
        return []
    except (httpx.RequestError, Exception):
        return []


async def _select_instance(service_name: str) -> dict | None:
    """
    Pilih satu instance dari daftar healthy.
    Sekarang: pick random dari healthy instances.
    Nanti Orang 2 bisa ganti jadi round-robin via discovery load balancer.
    """
    import random
    instances = await _get_healthy_instances(service_name)
    if not instances:
        return None
    return random.choice(instances)


def _build_backend_url(instance: dict, path: str) -> str:
    host = instance["host"]
    port = instance["port"]
    return f"http://{host}:{port}{path}"


def _build_forward_headers(request: Request, backend_url: str) -> dict:
    headers = {
        "X-Forwarded-For": request.client.host if request.client else "unknown",
        "X-Request-ID": str(uuid.uuid4()),
        "X-Gateway": "api-gateway",
    }
    # Forward header asli client (kecuali hop-by-hop)
    skip = {"host", "transfer-encoding", "connection", "keep-alive"}
    for key, value in request.headers.items():
        if key.lower() not in skip:
            headers[key] = value
    return headers


async def reverse_proxy_handler(request: Request):
    """
    Final handler untuk middleware pipeline.
    Parse path → cari route → query discovery → forward request ke backend.
    Return response dalam format StandardResponse.
    """
    path = request.url.path
    request_id = str(uuid.uuid4())

    # --- 1. Cari route ---
    route = get_route(path)
    if route is None:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": f"Tidak ada route untuk path: {path}",
                "request_id": request_id,
                "data": None,
            },
        )

    service_name = route["service_name"]
    prefix = route["prefix"]
    backend_path = path[len(prefix):] if route.get("strip_prefix") else path
    if not backend_path.startswith("/"):
        backend_path = "/" + backend_path

    # --- 2. Cek circuit breaker (opsional, via Orang 3) ---
    try:
        client = await _get_client()
        cb_resp = await client.get(f"{RESILIENCE_URL}/circuit/{service_name}")
        if cb_resp.status_code == 200:
            cb_state = cb_resp.json().get("state", "closed")
            if cb_state == "open":
                return JSONResponse(
                    status_code=503,
                    content={
                        "success": False,
                        "error": f"Circuit breaker OPEN untuk {service_name}, service tidak tersedia",
                        "request_id": request_id,
                        "data": None,
                    },
                )
    except Exception:
        pass  # resilience belum jalan, skip circuit check

    # --- 3. Pilih instance dari discovery ---
    instance = await _select_instance(service_name)
    if instance is None:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": f"Tidak ada instance healthy untuk {service_name}",
                "request_id": request_id,
                "data": None,
            },
        )

    # --- 4. Forward request ke backend ---
    backend_url = _build_backend_url(instance, backend_path)
    headers = _build_forward_headers(request, backend_url)
    body = await request.body()
    query = str(request.url.query) if request.url.query else ""

    try:
        client = await _get_client()
        backend_response = await client.request(
            method=request.method,
            url=backend_url,
            headers=headers,
            content=body if body else None,
            params=query,
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "error": f"Gagal menghubungi backend: {str(e)}",
                "request_id": request_id,
                "data": None,
            },
        )

    # --- 5. Parse response dari backend ---
    try:
        backend_data = backend_response.json()
    except Exception:
        backend_data = {"raw": backend_response.text}

    # --- 6. Wrap dalam StandardResponse ---
    success = 200 <= backend_response.status_code < 400

    return JSONResponse(
        status_code=backend_response.status_code,
        content={
            "success": success,
            "data": backend_data if success else None,
            "error": backend_data.get("detail", backend_data.get("error")) if not success else None,
            "request_id": request_id,
        },
    )
