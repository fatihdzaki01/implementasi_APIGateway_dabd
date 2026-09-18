import asyncio
import logging
import time
from typing import Dict, List, Optional
from app.models import ServiceInstance, InstanceStatus, RegisterRequest
from app.config import settings

logger = logging.getLogger("service_registry")

class ServiceRegistry:
    def __init__(self):
        # Format: { service_name: { instance_id: ServiceInstance } }
        self._registry: Dict[str, Dict[str, ServiceInstance]] = {}
        self._lock = asyncio.Lock()

    async def register(self, req: RegisterRequest) -> ServiceInstance:
        async with self._lock:
            instance_id = req.instance_id or f"{req.service_name}_{req.host}_{req.port}"
            
            if req.service_name not in self._registry:
                self._registry[req.service_name] = {}

            existing = self._registry[req.service_name].get(instance_id)
            if existing:
                existing.host = req.host
                existing.port = req.port
                existing.last_heartbeat = time.time()
                existing.status = InstanceStatus.HEALTHY
                if req.weight is not None:
                    existing.weight = req.weight
                if req.metadata:
                    existing.metadata.update(req.metadata)
                logger.info(f"[REGISTRY] Updated existing instance: {instance_id}")
                return existing

            instance = ServiceInstance(
                instance_id=instance_id,
                service_name=req.service_name,
                host=req.host,
                port=req.port,
                status=InstanceStatus.HEALTHY,
                last_heartbeat=time.time(),
                weight=req.weight or 1,
                metadata=req.metadata or {}
            )
            self._registry[req.service_name][instance_id] = instance
            logger.info(f"[REGISTRY] Registered new instance: {instance_id} at {instance.url}")
            return instance

    async def deregister(self, service_name: str, instance_id: str) -> bool:
        async with self._lock:
            if service_name in self._registry and instance_id in self._registry[service_name]:
                del self._registry[service_name][instance_id]
                if not self._registry[service_name]:
                    del self._registry[service_name]
                logger.info(f"[REGISTRY] Deregistered instance: {instance_id} from service {service_name}")
                return True
            logger.warning(f"[REGISTRY] Deregister failed: instance {instance_id} not found in {service_name}")
            return False

    async def record_heartbeat(self, service_name: str, instance_id: str) -> bool:
        async with self._lock:
            if service_name in self._registry and instance_id in self._registry[service_name]:
                instance = self._registry[service_name][instance_id]
                instance.last_heartbeat = time.time()
                # If instance was UNKNOWN due to missing heartbeat, restore to HEALTHY
                if instance.status == InstanceStatus.UNKNOWN:
                    instance.status = InstanceStatus.HEALTHY
                logger.debug(f"[REGISTRY] Heartbeat recorded for {instance_id}")
                return True
            return False

    async def update_status(self, service_name: str, instance_id: str, status: InstanceStatus) -> bool:
        """Called by Orang 3 (Health Checker) to update instance status."""
        async with self._lock:
            if service_name in self._registry and instance_id in self._registry[service_name]:
                old_status = self._registry[service_name][instance_id].status
                self._registry[service_name][instance_id].status = status
                logger.info(f"[REGISTRY] Status updated for {instance_id}: {old_status} -> {status}")
                return True
            return False

    async def get_instances(self, service_name: str, healthy_only: bool = True) -> List[ServiceInstance]:
        async with self._lock:
            if service_name not in self._registry:
                return []
            instances = list(self._registry[service_name].values())
            if healthy_only:
                return [inst for inst in instances if inst.status == InstanceStatus.HEALTHY]
            return instances

    async def get_all_services(self) -> Dict[str, List[ServiceInstance]]:
        async with self._lock:
            return {
                service_name: list(instances.values())
                for service_name, instances in self._registry.items()
            }

    async def cleanup_stale_instances(self, ttl_seconds: int = None) -> List[str]:
        """Removes or marks instances whose last heartbeat is older than TTL."""
        if ttl_seconds is None:
            ttl_seconds = settings.HEARTBEAT_TTL_SECONDS
            
        now = time.time()
        removed_ids = []
        async with self._lock:
            for service_name in list(self._registry.keys()):
                for instance_id, instance in list(self._registry[service_name].items()):
                    elapsed = now - instance.last_heartbeat
                    if elapsed > ttl_seconds:
                        logger.warning(
                            f"[REGISTRY] Heartbeat timeout ({elapsed:.1f}s > {ttl_seconds}s) for {instance_id}. Removing instance."
                        )
                        del self._registry[service_name][instance_id]
                        removed_ids.append(instance_id)
                if not self._registry[service_name]:
                    del self._registry[service_name]
        return removed_ids


# Global singleton instance
registry = ServiceRegistry()
