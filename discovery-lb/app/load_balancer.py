import asyncio
import logging
from typing import Dict, List, Optional
from app.models import ServiceInstance, LoadBalanceStrategy, InstanceStatus
from app.registry import ServiceRegistry

logger = logging.getLogger("load_balancer")

class NoHealthyInstanceException(Exception):
    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"No healthy instance available for service: '{service_name}'")

class LoadBalancer:
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        # Pointer map for Round Robin per service: { service_name: index }
        self._rr_counters: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def select_instance(
        self,
        service_name: str,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN
    ) -> ServiceInstance:
        """Selects the next healthy service instance based on the chosen strategy."""
        healthy_instances = await self.registry.get_instances(service_name, healthy_only=True)
        
        if not healthy_instances:
            logger.error(f"[LOAD_BALANCER] Request failed for service '{service_name}': 0 healthy instances found.")
            raise NoHealthyInstanceException(service_name)

        if strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return await self._round_robin(service_name, healthy_instances)
        elif strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return self._least_connections(healthy_instances)
        elif strategy == LoadBalanceStrategy.WEIGHTED:
            return await self._weighted_round_robin(service_name, healthy_instances)
        else:
            return await self._round_robin(service_name, healthy_instances)

    async def _round_robin(self, service_name: str, instances: List[ServiceInstance]) -> ServiceInstance:
        """Standard Round Robin algorithm with thread-safe counter."""
        async with self._lock:
            current_index = self._rr_counters.get(service_name, 0)
            selected = instances[current_index % len(instances)]
            self._rr_counters[service_name] = (current_index + 1) % len(instances)
            logger.debug(
                f"[LOAD_BALANCER] Round Robin for '{service_name}': selected instance {selected.instance_id} ({selected.url})"
            )
            return selected

    def _least_connections(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Least Connections algorithm: picks instance with minimum active connections."""
        selected = min(instances, key=lambda inst: inst.active_connections)
        logger.debug(
            f"[LOAD_BALANCER] Least Connections: selected {selected.instance_id} with {selected.active_connections} active connections."
        )
        return selected

    async def _weighted_round_robin(self, service_name: str, instances: List[ServiceInstance]) -> ServiceInstance:
        """Weighted Round Robin: builds weighted list and applies round-robin counter."""
        weighted_pool: List[ServiceInstance] = []
        for inst in instances:
            weight = max(1, inst.weight)
            weighted_pool.extend([inst] * weight)

        async with self._lock:
            current_index = self._rr_counters.get(f"{service_name}_weighted", 0)
            selected = weighted_pool[current_index % len(weighted_pool)]
            self._rr_counters[f"{service_name}_weighted"] = (current_index + 1) % len(weighted_pool)
            logger.debug(
                f"[LOAD_BALANCER] Weighted RR for '{service_name}': selected {selected.instance_id} (weight={selected.weight})"
            )
            return selected
