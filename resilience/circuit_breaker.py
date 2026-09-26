import time
import logging

logger = logging.getLogger("resilience.circuit_breaker")


class CircuitBreaker:
    def __init__(self, fail_threshold: int = 3, cooldown_seconds: float = 10.0):
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state: str = "closed"
        self.failure_count: int = 0
        self.opened_at: float | None = None

    def should_try(self) -> bool:
        if self.state == "open":
            elapsed = time.time() - self.opened_at
            if elapsed < self.cooldown_seconds:
                return False
            logger.info(f"[CB] OPEN → HALF_OPEN setelah {elapsed:.1f}s cooldown")
            self.state = "half_open"
            return True
        return True

    def on_success(self) -> None:
        if self.state != "closed":
            logger.info(f"[CB] {self.state.upper()} → CLOSED (recovery)")
        self.state = "closed"
        self.failure_count = 0
        self.opened_at = None

    def on_failure(self) -> None:
        self.failure_count += 1
        if self.state == "half_open":
            logger.warning("[CB] HALF_OPEN → OPEN (percobaan recovery gagal)")
            self.state = "open"
            self.opened_at = time.time()
        elif self.failure_count >= self.fail_threshold:
            logger.warning(f"[CB] CLOSED → OPEN (gagal {self.failure_count}x berturut-turut)")
            self.state = "open"
            self.opened_at = time.time()

    def __repr__(self) -> str:
        return f"CircuitBreaker(state={self.state}, failures={self.failure_count}/{self.fail_threshold})"
