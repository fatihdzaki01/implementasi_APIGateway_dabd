import sys
import os
import asyncio
import httpx
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from health_checker import check_health
from resilience_manager import ResilienceManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("resilience")

DISCOVERY_URL = os.getenv("DISCOVERY_URL", "http://discovery-lb:8010")

manager = ResilienceManager(
    fail_threshold=config.FAIL_THRESHOLD,
    cooldown_seconds=config.COOLDOWN_SECONDS,
)


async def get_all_instances() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{DISCOVERY_URL}/services")
            if r.status_code == 200:
                services = r.json().get("services", {})
                all_instances = []
                for service_name, instances in services.items():
                    for inst in instances:
                        inst["service_name"] = service_name
                        all_instances.append(inst)
                return all_instances
    except Exception as e:
        logger.warning(f"[RESILIENCE] Gagal fetch services dari discovery-lb: {e}")
    return []


async def get_instances_for_service(service_name: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{DISCOVERY_URL}/services/{service_name}?healthy_only=false")
            if r.status_code == 200:
                data = r.json()
                return data.get("instances", [])
    except Exception as e:
        logger.warning(f"[RESILIENCE] Gagal fetch instances {service_name}: {e}")
    return []


async def update_instance_status(service_name: str, instance_id: str, status: str, reason: str = "") -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.patch(
                f"{DISCOVERY_URL}/services/{service_name}/instances/{instance_id}/status",
                json={"status": status, "reason": reason},
            )
            if r.status_code == 200:
                logger.info(f"[RESILIENCE] Updated {service_name}/{instance_id} -> {status}")
            else:
                logger.warning(f"[RESILIENCE] Gagal update status {instance_id}: HTTP {r.status_code}")
    except Exception as e:
        logger.warning(f"[RESILIENCE] Gagal call discovery-lb untuk update status: {e}")


async def poll_service(service_name: str, svc_instances: list[dict]) -> bool:
    any_healthy = False
    for inst in svc_instances:
        instance_id = inst.get("instance_id", "")
        host        = inst.get("host", "")
        port        = inst.get("port", 0)

        if not all([instance_id, host, port]):
            continue

        is_healthy = await check_health(host, port, timeout=config.REQUEST_TIMEOUT)

        if is_healthy:
            any_healthy = True
            await update_instance_status(service_name, instance_id, "HEALTHY", "health check passed")
        else:
            await update_instance_status(
                service_name, instance_id, "UNHEALTHY",
                f"health check failed (circuit state: {manager.get_state(service_name)['state']})"
            )
            logger.warning(f"[RESILIENCE] {service_name}/{instance_id} UNHEALTHY")

    return any_healthy


async def health_check_loop():
    logger.info("[RESILIENCE] Health check loop started.")
    while True:
        instances = await get_all_instances()

        services: dict[str, list[dict]] = {}
        for inst in instances:
            svc = inst.get("service_name", "")
            if svc:
                services.setdefault(svc, []).append(inst)

        for service_name, svc_instances in services.items():
            cb_state = manager.get_state(service_name)["state"]

            if cb_state == "half_open":
                logger.debug(f"[RESILIENCE] Circuit HALF_OPEN untuk {service_name} — menunggu probe manual.")
                continue

            if cb_state == "open":
                if not manager.should_try(service_name):
                    logger.debug(f"[RESILIENCE] Circuit OPEN untuk {service_name}, cooldown belum selesai.")
                    continue
                cb_state = manager.get_state(service_name)["state"]

            any_healthy = await poll_service(service_name, svc_instances)

            if any_healthy:
                if cb_state != "half_open":
                    manager.record_success(service_name)
            else:
                manager.record_failure(service_name)
                logger.warning(
                    f"[RESILIENCE] Semua instance {service_name} UNHEALTHY — "
                    f"CB state: {manager.get_state(service_name)['state']}, "
                    f"failures: {manager.get_state(service_name)['failure_count']}"
                )

        await asyncio.sleep(config.CHECK_INTERVAL)


async def do_probe(service_name: str) -> dict:
    instances = await get_instances_for_service(service_name)

    if not instances:
        manager.record_failure(service_name)
        return {
            "service_name": service_name,
            "probe_result": "failed",
            "reason": "no instances found",
            **manager.get_state(service_name)
        }

    for inst in instances:
        instance_id = inst.get("instance_id", "")
        host        = inst.get("host", "")
        port        = inst.get("port", 0)

        if not all([instance_id, host, port]):
            continue

        is_healthy = await check_health(host, port, timeout=config.REQUEST_TIMEOUT)

        if is_healthy:
            manager.record_success(service_name)
            await update_instance_status(service_name, instance_id, "HEALTHY", "probe passed")
            return {
                "service_name": service_name,
                "probe_result": "success",
                "probed_instance": instance_id,
                **manager.get_state(service_name)
            }

    manager.record_failure(service_name)
    return {
        "service_name": service_name,
        "probe_result": "failed",
        "reason": "all instances unhealthy",
        **manager.get_state(service_name)
    }


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
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Resilience Service", description="Health Check & Circuit Breaker", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "resilience"}


@app.get("/circuit/{service_name}")
async def get_circuit_state(service_name: str):
    return manager.get_state(service_name)


@app.post("/circuit/{service_name}/probe")
async def probe_circuit(service_name: str):
    state = manager.get_state(service_name)["state"]
    if state != "half_open":
        return {
            "service_name": service_name,
            "probe_result": "skipped",
            "reason": f"circuit state is '{state}', probe only allowed in half_open",
            **manager.get_state(service_name)
        }
    return await do_probe(service_name)


@app.get("/status")
async def status():
    return {"circuit_breakers": manager.get_all_states()}
