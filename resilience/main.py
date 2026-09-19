"""
Resilience Service — FastAPI app entrypoint.
Orang 3 (resilience) yang maintain file ini.

Menjalankan health checker + circuit breaker sebagai background worker.
"""

import sys
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Pastikan parent directory ada di sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
import mock_registry as registry
from resilience_manager import CircuitBreaker, ResilienceManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("  Resilience Service — Starting...")
    print("=" * 60)
    print(f"  CHECK_INTERVAL : {config.CHECK_INTERVAL}s")
    print(f"  FAIL_THRESHOLD : {config.FAIL_THRESHOLD}")
    print(f"  COOLDOWN       : {config.COOLDOWN_SECONDS}s")
    print(f"  Services       : {list(registry.get_all_services().keys())}")
    print("=" * 60)

    # Jalankan health checker di background
    async def _run_health_checker():
        while True:
            for service_name in list(registry.get_all_services().keys()):
                try:
                    url = registry.get_url(service_name)
                    import httpx
                    async with httpx.AsyncClient() as client:
                        r = await client.get(url, timeout=config.REQUEST_TIMEOUT)
                        if r.status_code == 200:
                            registry.set_status(service_name, "healthy")
                        else:
                            registry.set_status(service_name, "unhealthy")
                except Exception:
                    registry.set_status(service_name, "unhealthy")
            await asyncio.sleep(config.CHECK_INTERVAL)

    task = asyncio.create_task(_run_health_checker())
    print("Resilience health checker started.")
    yield
    task.cancel()
    print("Resilience Service — Shutdown complete.")


app = FastAPI(
    title="Resilience Service",
    description="Health Check & Circuit Breaker",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "resilience"}


@app.get("/status")
async def status():
    services = registry.get_all_services()
    return {
        "services": {
            name: {"status": info["status"], "host": info["host"], "port": info["port"]}
            for name, info in services.items()
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8020)
