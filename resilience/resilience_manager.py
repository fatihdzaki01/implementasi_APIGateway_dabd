import time
import httpx
import mock_registry as registry
import config


class CircuitBreaker:
    """Satu circuit breaker = satu state mesin buat SATU service."""

    def __init__(self, fail_threshold=config.FAIL_THRESHOLD,
                 cooldown_seconds=config.COOLDOWN_SECONDS):
        self.state = "closed"          # closed | open | half_open
        self.failure_count = 0
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_seconds
        self.opened_at = None

    def should_try(self):
        """Cek apakah boleh kirim request sekarang."""
        if self.state == "open":
            elapsed = time.time() - self.opened_at
            if elapsed < self.cooldown_seconds:
                return False
            else:
                self.state = "half_open"
                return True
        return True  # closed atau half_open boleh nyoba

    def on_success(self):
        self.state = "closed"
        self.failure_count = 0

    def on_failure(self):
        self.failure_count += 1
        if self.state == "half_open":
            self.state = "open"
            self.opened_at = time.time()
        elif self.failure_count >= self.fail_threshold:
            self.state = "open"
            self.opened_at = time.time()


class ResilienceManager:
    """Ngatur health check + circuit breaker buat SEMUA service."""

    def __init__(self, check_interval=config.CHECK_INTERVAL):
        self.check_interval = check_interval
        self.breakers = {}  # service_name -> CircuitBreaker

        # Bikin 1 circuit breaker untuk tiap service yang ada di registry
        for service_name in registry.get_all_services():
            self.breakers[service_name] = CircuitBreaker()

    def check_one(self, service_name):
        breaker = self.breakers[service_name]

        if not breaker.should_try():
            # Lagi OPEN, cooldown belum selesai -> skip, jangan nembak beneran
            registry.set_status(service_name, "unhealthy (circuit open)")
            return

        url = registry.get_url(service_name)
        try:
            r = httpx.get(url, timeout=config.REQUEST_TIMEOUT)
            if r.status_code == 200:
                breaker.on_success()
                registry.set_status(service_name, "healthy")
            else:
                breaker.on_failure()
                registry.set_status(service_name, "unhealthy")
        except Exception:
            breaker.on_failure()
            registry.set_status(service_name, "unhealthy")

    def run_forever(self):
        print("Resilience manager jalan, memonitor service:",
              list(self.breakers.keys()))
        while True:
            for service_name in self.breakers:
                self.check_one(service_name)
            print("---")
            time.sleep(self.check_interval)


if __name__ == "__main__":
    manager = ResilienceManager()
    manager.run_forever()