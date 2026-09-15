import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import (
    RegisterRequest,
    DeregisterRequest,
    HeartbeatRequest,
    StatusUpdateRequest,
    ServiceInstance,
    LoadBalanceStrategy,
    InstanceStatus,
)
from app.registry import registry
from app.load_balancer import LoadBalancer, NoHealthyInstanceException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("discovery_lb_api")

load_balancer = LoadBalancer(registry)

# Background task for heartbeat cleanup
cleanup_task: Optional[asyncio.Task] = None

async def periodic_cleanup():
    """Periodically cleans up stale instances that missed heartbeat TTL."""
    while True:
        try:
            await asyncio.sleep(settings.CLEANUP_INTERVAL_SECONDS)
            removed = await registry.cleanup_stale_instances(settings.HEARTBEAT_TTL_SECONDS)
            if removed:
                logger.info(f"[CLEANUP] Automatically pruned stale instances: {removed}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[CLEANUP] Error during periodic cleanup: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background cleanup loop
    global cleanup_task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("[SERVER] Service Discovery & Load Balancer started.")
    yield
    # Shutdown: Cancel cleanup task
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("[SERVER] Service Discovery & Load Balancer stopped.")

app = FastAPI(
    title="Service Discovery & Load Balancer API",
    description="Orang 2 Module: Service Registry, Auto-Registration, Round-Robin Load Balancer & Health Integration",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {
        "service": "Service Discovery & Load Balancer",
        "role": "Orang 2",
        "status": "running",
        "heartbeat_ttl_seconds": settings.HEARTBEAT_TTL_SECONDS
    }

# --------------------------------------------------------------------------
# Service Registration & Management Endpoints
# --------------------------------------------------------------------------

@app.post("/register", response_model=Dict, status_code=status.HTTP_201_CREATED)
async def register_service(req: RegisterRequest):
    """
    Instance registration endpoint.
    Called automatically by service instances when starting up.
    """
    instance = await registry.register(req)
    return {
        "message": "Instance registered successfully",
        "data": instance.to_contract_dict()
    }

@app.post("/deregister", response_model=Dict)
async def deregister_service(req: DeregisterRequest):
    """
    Instance deregistration endpoint.
    Called when an instance shuts down cleanly.
    """
    success = await registry.deregister(req.service_name, req.instance_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance '{req.instance_id}' for service '{req.service_name}' not found."
        )
    return {"message": "Instance deregistered successfully", "instance_id": req.instance_id}

@app.post("/heartbeat", response_model=Dict)
async def receive_heartbeat(req: HeartbeatRequest):
    """
    Heartbeat endpoint.
    Called periodically by instances to refresh their active timestamp.
    """
    success = await registry.record_heartbeat(req.service_name, req.instance_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance '{req.instance_id}' not found in registry. Please re-register."
        )
    return {"message": "Heartbeat acknowledged", "instance_id": req.instance_id}

@app.get("/services", response_model=Dict)
async def list_services():
    """Lists all registered services and their instances."""
    services = await registry.get_all_services()
    formatted = {
        name: [inst.to_contract_dict() for inst in inst_list]
        for name, inst_list in services.items()
    }
    return {"services": formatted}

@app.get("/services/{service_name}", response_model=Dict)
async def get_service(service_name: str, healthy_only: bool = Query(default=False)):
    """Returns instances of a specific service."""
    instances = await registry.get_instances(service_name, healthy_only=healthy_only)
    return {
        "service_name": service_name,
        "count": len(instances),
        "instances": [inst.to_contract_dict() for inst in instances]
    }

# --------------------------------------------------------------------------
# Integration Contract Endpoints for Orang 1 (Gateway) & Orang 3 (Health Checker)
# --------------------------------------------------------------------------

@app.get("/lb/next/{service_name}")
async def get_next_instance(
    service_name: str,
    strategy: LoadBalanceStrategy = Query(default=LoadBalanceStrategy.ROUND_ROBIN)
):
    """
    ENDPOINT UNTUK ORANG 1 (API GATEWAY):
    Mengembalikan instance sehat berikutnya untuk merutekan request HTTP.
    Mendukung strategi: round_robin, least_conn, weighted.
    """
    try:
        instance = await load_balancer.select_instance(service_name, strategy=strategy)
        return {
            "status": "success",
            "service_name": service_name,
            "strategy": strategy.value,
            "target": instance.to_contract_dict()
        }
    except NoHealthyInstanceException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )

@app.patch("/services/{service_name}/instances/{instance_id}/status")
async def update_instance_status(
    service_name: str,
    instance_id: str,
    payload: StatusUpdateRequest
):
    """
    ENDPOINT UNTUK ORANG 3 (HEALTH CHECKER):
    Diperbarui oleh modul Health Checker ketika health check instance gagal/sukses.
    """
    success = await registry.update_status(service_name, instance_id, payload.status)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance '{instance_id}' for service '{service_name}' not found."
        )
    return {
        "message": f"Status for {instance_id} updated to {payload.status.value}",
        "instance_id": instance_id,
        "status": payload.status.value,
        "reason": payload.reason
    }
