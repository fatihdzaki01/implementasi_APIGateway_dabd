"""
Mock Registry - pengganti sementara punya Orang 2 (Service Discovery)
Nanti pas fase integrasi, file ini tinggal dibuang dan diganti
manggil registry beneran punya Orang 2, selama bentuk datanya sama.
"""

# Data awal: daftar service yang mau dimonitor
# Nanti ini yang bakal diisi otomatis oleh Orang 2 pas service registrasi sendiri
registry = {
    "service-a": {"host": "service-a", "port": 8001, "status": "unknown"},
    "service-b": {"host": "service-b", "port": 8002, "status": "unknown"},
    "service-c": {"host": "service-c", "port": 8003, "status": "unknown"},
}


def get_all_services():
    """Ambil semua service yang terdaftar."""
    return registry


def set_status(service_name, status):
    """Update status satu service. Dipanggil oleh health checker."""
    if service_name in registry:
        old_status = registry[service_name]["status"]
        registry[service_name]["status"] = status
        if old_status != status:
            print(f"[REGISTRY] {service_name}: {old_status} -> {status}")


def get_url(service_name):
    """Bikin URL health check dari data registry."""
    svc = registry[service_name]
    return f"http://{svc['host']}:{svc['port']}/health"