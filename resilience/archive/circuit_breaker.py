import time
import httpx

class CircuitBreaker:
    def __init__(self, fail_threshold=3, cooldown_seconds=10):
        self.state = "closed"          # closed | open | half_open
        self.failure_count = 0
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_seconds
        self.opened_at = None

    def call(self, url):
        # Kalau lagi OPEN, cek dulu apakah sudah waktunya coba lagi
        if self.state == "open":
            elapsed = time.time() - self.opened_at
            if elapsed < self.cooldown_seconds:
                print(f"[OPEN] Menolak request, masih cooldown ({elapsed:.1f}s)")
                return None
            else:
                print("[OPEN -> HALF_OPEN] Waktunya coba lagi")
                self.state = "half_open"

        # State closed atau half_open, coba kirim request beneran
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                self._on_success()
                return r.json()
            else:
                self._on_failure()
                return None
        except Exception:
            self._on_failure()
            return None

    def _on_success(self):
        if self.state == "half_open":
            print("[HALF_OPEN -> CLOSED] Percobaan berhasil, normal lagi")
        self.state = "closed"
        self.failure_count = 0

    def _on_failure(self):
        self.failure_count += 1
        print(f"[FAIL] Gagal ke-{self.failure_count}")

        if self.state == "half_open":
            print("[HALF_OPEN -> OPEN] Percobaan gagal, balik ditutup")
            self.state = "open"
            self.opened_at = time.time()
        elif self.failure_count >= self.fail_threshold:
            print(f"[CLOSED -> OPEN] Gagal {self.failure_count}x beruntun, sekring jeglek")
            self.state = "open"
            self.opened_at = time.time()


# --- coba pakai ---
if __name__ == "__main__":
    breaker = CircuitBreaker(fail_threshold=3, cooldown_seconds=10)

    while True:
        result = breaker.call("http://localhost:8001/health")
        print("Hasil:", result, "| State sekarang:", breaker.state)
        print("---")
        time.sleep(2)