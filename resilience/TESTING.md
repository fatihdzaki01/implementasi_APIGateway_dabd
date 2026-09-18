# Dokumentasi Testing - Health Check & Circuit Breaker (Orang 3)

## 1. Ringkasan Modul

Modul ini bertugas memonitor kesehatan tiap service secara berkala (health
check) dan menghentikan pengiriman request ke service yang bermasalah
secara otomatis (circuit breaker), supaya sistem tidak buang waktu terus
menembak service yang sedang down.

## 2. Cara Menjalankan

1. Jalankan dummy service di beberapa port (contoh: 8001, 8002, 8003)
   ```
   uvicorn dummy_service:app --port 8001
   uvicorn dummy_service:app --port 8002
   uvicorn dummy_service:app --port 8003
   ```
2. Jalankan resilience manager
   ```
   python resilience_manager.py
   ```

## 3. Parameter yang Dipakai (lihat config.py)

| Parameter | Nilai | Keterangan |
|---|---|---|
| FAIL_THRESHOLD | 3 | Gagal berturut-turut sebelum circuit OPEN |
| COOLDOWN_SECONDS | 10 | Lama tunggu sebelum coba HALF_OPEN |
| CHECK_INTERVAL | 3 | Jeda antar polling ke semua service (detik) |
| REQUEST_TIMEOUT | 2 | Timeout tiap request health check (detik) |

## 4. Skenario Testing

### Skenario 1 - Semua service sehat
**Langkah:** Nyalakan ketiga dummy service, jalankan resilience manager.
**Ekspektasi:** Semua service berubah status dari `unknown` menjadi `healthy`.
**Hasil:** [isi: sesuai / tidak, screenshot log]

### Skenario 2 - Satu service mati
**Langkah:** Matikan salah satu dummy service (Ctrl+C), biarkan manager tetap jalan.
**Ekspektasi:** Setelah beberapa kali gagal, status berubah `healthy -> unhealthy`,
lalu setelah mencapai FAIL_THRESHOLD, berubah jadi `unhealthy (circuit open)`.
**Hasil:** [isi: sesuai / tidak, screenshot log]

### Skenario 3 - Circuit tidak menembak saat OPEN
**Langkah:** Perhatikan log setelah circuit OPEN, apakah masih mencoba
request ke service yang mati atau langsung skip.
**Ekspektasi:** Tidak ada percobaan request baru sampai COOLDOWN_SECONDS lewat
(hemat waktu, tidak menunggu timeout tiap kali).
**Hasil:** [isi]

### Skenario 4 - Service hidup lagi (recovery)
**Langkah:** Setelah circuit OPEN, nyalakan lagi dummy service yang mati
tadi, tunggu sampai cooldown selesai.
**Ekspektasi:** Circuit masuk HALF_OPEN, coba request lagi, berhasil,
lalu balik ke status `healthy` (closed).
**Hasil:** [isi]

### Skenario 5 - Banyak service, satu mati satu hidup
**Langkah:** Matikan 1 dari 3 service, biarkan 2 lainnya tetap hidup.
**Ekspektasi:** Status tiap service independen -- yang mati jadi unhealthy,
yang lain tetap healthy (circuit breaker per-service, bukan global).
**Hasil:** [isi]

## 5. Kontrak / Interface untuk Integrasi

Modul ini bergantung pada 3 fungsi dari service registry (saat ini pakai
mock_registry.py sebagai pengganti sementara punya Orang 2):

- `get_all_services()` -> dict semua service terdaftar
- `set_status(service_name, status)` -> update status satu service
- `get_url(service_name)` -> return URL health check

Untuk gateway (Orang 1), circuit breaker bisa diakses melalui fungsi
`should_try(service_name)` sebelum forward request, agar request tidak
dikirim ke service yang sedang OPEN.

## 6. Catatan / Kendala