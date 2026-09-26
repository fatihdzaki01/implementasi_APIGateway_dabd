import logging
from typing import Dict

import config
from circuit_breaker import CircuitBreaker

logger = logging.getLogger("resilience.manager")


class ResilienceManager:
    def __init__(self, fail_threshold: int = config.FAIL_THRESHOLD, cooldown_seconds: float = config.COOLDOWN_SECONDS):
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_seconds
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_or_create(self, service_name: str) -> CircuitBreaker:
        if service_name not in self._breakers:
            self._breakers[service_name] = CircuitBreaker(
                fail_threshold=self.fail_threshold,
                cooldown_seconds=self.cooldown_seconds,
            )
            logger.info(f"[MANAGER] CircuitBreaker baru dibuat untuk: {service_name}")
        return self._breakers[service_name]

    def should_try(self, service_name: str) -> bool:
        if service_name not in self._breakers:
            return True
        return self._breakers[service_name].should_try()

    def record_success(self, service_name: str) -> None:
        self.get_or_create(service_name).on_success()

    def record_failure(self, service_name: str) -> None:
        self.get_or_create(service_name).on_failure()

    def get_state(self, service_name: str) -> dict:
        if service_name not in self._breakers:
            return {"service_name": service_name, "state": "closed", "failure_count": 0, "opened_at": None}
        cb = self._breakers[service_name]
        return {"service_name": service_name, "state": cb.state, "failure_count": cb.failure_count, "opened_at": cb.opened_at}

    def get_all_states(self) -> Dict[str, dict]:
        return {name: self.get_state(name) for name in self._breakers}

    def __repr__(self) -> str:
        return f"ResilienceManager(services={list(self._breakers.keys())})"
