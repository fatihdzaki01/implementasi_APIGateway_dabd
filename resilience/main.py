"""
Resilience Service — FastAPI app entrypoint.
Orang 3 (resilience) yang maintain file ini.

Menjalankan health checker + circuit breaker sebagai background worker.
Update status ke discovery-lb (Orang 2) via HTTP, bukan in-memory mock.

Endpoints yang disediakan untuk Orang 1 (gateway):
    GET /circuit/{service_name}  → return state circuit breaker
    GET /health                  → health check resilience service itu sendiri
    GET /status                  → lihat status semua service yang dimonitor
"""

import sys
import os
import asyncio
import httpx
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from resilience_manager import CircuitBreaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("resilience")

# ============================================================
# URL ke discovery-lb (Orang 2)
# ============================================================
DISCOVERY_URL = os.getenv("DISCOVERY_URL", "http://discovery-lb:8010")

# ============================================================
# State: circuit breaker per (service_name, instance_id)
# Key: service_name → CircuitBreaker
# (1 CB per service, bukan per instance — cukup untuk demo)
# ============================================================
circuit_breakers: Dict[str, CircuitBreaker] = {}


# ============================================================
# Helpers
# ============================================================

async def get_all_instances() -> list[dict]:
    """
    Ambil semua instance dari discovery-lb.
    Return list of instance dicts.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{DISCOVERY_URL}/services")
            if r.status_code == 200:
                data = r.json()
                # format: {"services": {"service-a": [instance, ...], ...}}
                services = data.get("services", {})
                all_instances = []
                for service_name, instances in services.items():
                    for inst in instances:
                        inst["service_name"] = service_name
                        all_instances.append(inst)
                return all_instances
    except Exception as e:
        logger.warning(f"[RESILIENCE] Gagal fetch services dari discovery-lb: {e}")
    return []


async def update_instance_status(service_name: str, instance_id: str, status: str, reason: str = "") -> None:
    """
    Update status instance di discovery-lb (Orang 2).
    status: "HEALTHY" | "UNHEALTHY"
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.patch(
                f"{DISCOVERY_URL}/services/{service_name}/instances/{instance_id}/status",
                json={"status": status, "reason": reason},
            )
            if r.status_code == 200:
                logger.info(f"[RESILIENCE] Updated {service_name}/{instance_id} → {status}")
            else:
                logger.warning(f"[RESILIENCE] Gagal update status {instance_id}: HTTP {r.status_code}")
    except Exception as e:
        logger.warning(f"[RESILIENCE] Gagal call discovery-lb untuk update status: {e}")


async def check_health(host: str, port: int) -> bool:
    """Panggil /health endpoint satu instance. Return True jika sehat."""
    url = f"http://{host}:{port}/health"
    try:
        async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT) as client:
            r = await client.get(url)
            return r.status_code == 200
    except Exception:
        return False


# ============================================================
# Background health check + circuit breaker loop
# ============================================================

async def health_check_loop():
    """
    Polling ke /health tiap instance yang terdaftar di discovery-lb.
    Update status di discovery-lb dan ubah state circuit breaker.
    """
    logger.info("[RESILIENCE] Health check loop started.")
    while True:
        instances = await get_all_instances()

        for inst in instances:
            service_name = inst.get("service_name", "")
            instance_id  = inst.get("instance_id", "")
            host         = inst.get("host", "")
            port         = inst.get("port", 0)

            if not all([service_name, instance_id, host, port]):
                continue

            # Pastikan circuit breaker untuk service ini ada
            if service_name not in circuit_breakers:
                circuit_breakers[service_name] = CircuitBreaker(
                    fail_threshold=config.FAIL_THRESHOLD,
                    cooldown_seconds=config.COOLDOWN_SECONDS,
                )

            cb = circuit_breakers[service_name]

            # Kalau circuit OPEN dan belum waktunya half-open, skip poll
            if not cb.should_try():
                logger.debug(f"[RESILIENCE] Circuit OPEN untuk {service_name}, skip health check.")
                continue

            # Poll /health
            is_healthy = await check_health(host, port)

            if is_healthy:
                cb.on_success()
                await update_instance_status(service_name, instance_id, "HEALTHY", "health check passed")
            else:
                cb.on_failure()
                status = "UNHEALTHY"
                reason = f"health check failed (circuit state: {cb.state})"
                await update_instance_status(service_name, instance_id, status, reason)
                logger.warning(f"[RESILIENCE] {service_name}/{instance_id} UNHEALTHY, CB state: {cb.state}")

        await asyncio.sleep(config.CHECK_INTERVAL)


# ============================================================
# FastAPI app
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("  Resilience Service — Starting...")
    print("=" * 60)
    print(f"  DISCOVERY_URL  : {DISCOVERY_URL}")
    print(f"  CHECK_INTERVAL : {config.CHECK_INTERVAL}s")
    print(f"  FAIL_THRESHOLD : {config.FAIL_THRESHOLD}")
    print(f"  COOLDOWN       : {config.COOLDOWN_SECONDS}s")
    print("=" * 60)

    task = asyncio.create_task(health_check_loop())
    logger.info("[RESILIENCE] Health check background task started.")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("[RESILIENCE] Shutdown complete.")


app = FastAPI(
    title="Resilience Service",
    description="Health Check & Circuit Breaker — Orang 3",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check resilience service itu sendiri."""
    return {"status": "healthy", "service": "resilience"}


@app.get("/circuit/{service_name}")
async def get_circuit_state(service_name: str):
    """
    Endpoint untuk Orang 1 (gateway) — query state circuit breaker.

    Response:
        {
            "service_name": "service-a",
            "state": "closed" | "open" | "half_open",
            "failure_count": 3
        }

    Gateway harus menolak forward request ke service jika state == "open".
    """
    if service_name not in circuit_breakers:
        # Belum ada data → anggap closed (service belum pernah dicek)
        return {
            "service_name": service_name,
            "state": "closed",
            "failure_count": 0,
        }

    cb = circuit_breakers[service_name]
    return {
        "service_name": service_name,
        "state": cb.state,
        "failure_count": cb.failure_count,
    }


@app.get("/status")
async def status():
    """Lihat state semua circuit breaker yang aktif."""
    return {
        "circuit_breakers": {
            name: {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "opened_at": cb.opened_at,
            }
            for name, cb in circuit_breakers.items()
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8020)
