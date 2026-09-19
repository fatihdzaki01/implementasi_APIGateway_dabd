"""
Dummy Service B — Products service
Port: 8002
"""

import asyncio
from fastapi import FastAPI
from datetime import datetime
import httpx
import os

app = FastAPI(title="Service B", version="1.0.0")

SERVICE_NAME = "service-b"
HOST = os.getenv("SERVICE_HOST", "service-b")
PORT = int(os.getenv("SERVICE_PORT", "8002"))
DISCOVERY_URL = os.getenv("DISCOVERY_URL", "http://discovery-lb:8010")

INSTANCE_ID = f"{SERVICE_NAME}_{HOST}_{PORT}"

# In-memory dummy data
products = [
    {"id": 1, "name": "Monitor 24 inch", "price": 2500000, "stock": 10},
    {"id": 2, "name": "Webcam HD", "price": 450000, "stock": 25},
    {"id": 3, "name": "Headset USB", "price": 300000, "stock": 50},
]


@app.on_event("startup")
async def register_to_discovery():
    """Register diri ke service discovery saat startup + kirim heartbeat periodic."""
    async def _register_with_retry():
        for attempt in range(1, 20):
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        f"{DISCOVERY_URL}/register",
                        json={
                            "service_name": SERVICE_NAME,
                            "host": HOST,
                            "port": PORT,
                            "weight": 1,
                        },
                        timeout=5.0,
                    )
                    if r.status_code < 300:
                        print(f"[{SERVICE_NAME}] Berhasil register ke discovery")
                        return True
            except Exception as e:
                pass
            print(f"[{SERVICE_NAME}] Retry register ({attempt}/10)...")
            await asyncio.sleep(3)
        print(f"[{SERVICE_NAME}] Gagal register setelah 10 percobaan")
        return False

    registered = await _register_with_retry()

    async def _heartbeat_loop():
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{DISCOVERY_URL}/heartbeat",
                        json={"service_name": SERVICE_NAME, "instance_id": INSTANCE_ID},
                        timeout=5.0,
                    )
            except Exception:
                pass
            await asyncio.sleep(10)

    asyncio.create_task(_heartbeat_loop())


@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()}


@app.get("/products")
async def get_products():
    return {"products": products, "total": len(products)}


@app.get("/products/{product_id}")
async def get_product(product_id: int):
    for product in products:
        if product["id"] == product_id:
            return {"product": product}
    return {"error": "Product not found"}


@app.post("/products")
async def create_product(product: dict):
    new_product = {"id": len(products) + 1, **product}
    products.append(new_product)
    return {"product": new_product, "message": "Product created"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
