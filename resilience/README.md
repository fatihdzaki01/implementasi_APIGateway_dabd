# Resilience Module (Health Check & Circuit Breaker)

Modul ini bertugas memonitor kesehatan tiap service secara berkala (health
check) dan menghentikan pengiriman request ke service yang bermasalah
secara otomatis (circuit breaker), supaya sistem tidak buang waktu terus
menembak service yang sedang down.

## Struktur File

```
resilience/
 ├─ dummy_service.py       # service dummy buat testing, punya endpoint /health
 ├─ mock_registry.py       # pengganti sementara punya Orang 2 (Service Discovery)
 ├─ config.py              # semua parameter (threshold, cooldown, interval)
 ├─ resilience_manager.py  # program utama: health checker + circuit breaker
 ├─ TESTING.md             # dokumentasi hasil testing & skenario
 ├─ archive/               # file versi belajar (standalone, single service)
 └─ README.md              # file ini
```

## Cara Menjalankan

1. Install dependency:
   ```
   pip install fastapi uvicorn httpx
   ```

2. Jalankan dummy service di beberapa port (contoh: 8001, 8002, 8003) --
   tiap perintah di terminal terpisah:
   ```
   uvicorn dummy_service:app --port 8001
   uvicorn dummy_service:app --port 8002
   uvicorn dummy_service:app --port 8003
   ```

3. Jalankan resilience manager (di terminal lain):
   ```
   python resilience_manager.py
   ```

4. Coba matikan salah satu dummy service (Ctrl+C) untuk lihat circuit
   breaker bekerja: status berubah `healthy -> unhealthy -> unhealthy
   (circuit open)`, lalu otomatis coba lagi setelah cooldown.

## Cara Kerja Singkat

- **Health Checker**: tiap `CHECK_INTERVAL` detik, cek endpoint `/health`
  semua service yang terdaftar di registry.
- **Circuit Breaker**: per-service, punya 3 state:
  - `closed` -- normal, request jalan seperti biasa
  - `open` -- setelah gagal `FAIL_THRESHOLD` kali berturut-turut, request
    langsung ditolak tanpa mencoba (hemat waktu timeout)
  - `half_open` -- setelah `COOLDOWN_SECONDS`, dicoba sekali lagi. Kalau
    berhasil balik `closed`, kalau gagal balik `open`

## Kontrak / Interface untuk Integrasi

### Yang dibutuhkan modul ini dari Service Registry (Orang 2)

Saat ini pakai `mock_registry.py` sebagai pengganti sementara. Registry
asli nanti tinggal disambung selama menyediakan 3 fungsi ini:

| Fungsi | Return | Keterangan |
|---|---|---|
| `get_all_services()` | dict semua service terdaftar | dipakai untuk tahu service apa saja yang harus dimonitor |
| `set_status(service_name, status)` | - | dipanggil modul ini tiap ada perubahan status |
| `get_url(service_name)` | string URL | dipakai untuk hit endpoint `/health` |

Bentuk data 1 service:
```python
{"host": "localhost", "port": 8001, "status": "healthy"}
```

### Yang disediakan modul ini untuk Gateway (Orang 1)

`ResilienceManager` menyimpan 1 `CircuitBreaker` per service di
`self.breakers[service_name]`. Sebelum forward request ke suatu service,
gateway bisa cek dulu:

```python
breaker = manager.breakers[service_name]
if not breaker.should_try():
    # tolak request, balas 503 cepat tanpa nunggu timeout
```

## Status Pengerjaan

- [x] Health check multi-service
- [x] Circuit breaker per-service (closed/open/half-open)
- [x] Mock registry sebagai pengganti sementara
- [x] Config terpisah
- [ ] Sambung ke registry asli punya Orang 2 (menunggu fase integrasi)
- [ ] Sambung ke gateway punya Orang 1 (menunggu fase integrasi)