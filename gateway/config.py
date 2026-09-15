"""
Routing table — mapping path publik ke service internal.
Orang 1 (gateway) yang maintain file ini.
Tambahkan entry baru di sini untuk menambah route, tanpa ubah core gateway.
"""

# ============================================================
# ROUTING TABLE
# Key   : prefix path publik (dari client)
# Value : config routing ke service backend
# ============================================================

ROUTING_TABLE: dict[str, dict] = {
    "/service-a": {
        "service_name": "service-a",   # nama yang terdaftar di discovery registry
        "strip_prefix": True,           # /service-a/items → /items
    },
    "/service-b": {
        "service_name": "service-b",
        "strip_prefix": True,
    },
    "/service-c": {
        "service_name": "service-c",
        "strip_prefix": True,
    },
}


def get_route(path: str) -> dict | None:
    """
    Temukan config routing berdasarkan prefix path.
    Return None jika tidak ada route yang cocok.

    Contoh:
        get_route("/service-a/items")
        → {"service_name": "service-a", "strip_prefix": True}
    """
    for prefix, config in ROUTING_TABLE.items():
        if path.startswith(prefix):
            return {"prefix": prefix, **config}
    return None
