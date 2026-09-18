# Circuit Breaker
FAIL_THRESHOLD = 3        # gagal berturut-turut sebelum circuit OPEN
COOLDOWN_SECONDS = 10      # lama nunggu sebelum coba HALF_OPEN
 
# Health Checker
CHECK_INTERVAL = 3         # jeda antar polling ke semua service (detik)
REQUEST_TIMEOUT = 2        # timeout tiap request health check (detik)
 