"""
Dummy Service A — Items service
Port: 8001
"""

from fastapi import FastAPI
from datetime import datetime
import httpx
import os

app = FastAPI(title="Service A", version="1.0.0")

SERVICE_NAME = "service-a"
HOST = os.getenv("SERVICE_HOST", "service-a")
PORT = int(os.getenv("SERVICE_PORT", "8001"))
DISCOVERY_URL = os.getenv("DISCOVERY_URL", "http://discovery-lb:8010")

# In-memory dummy data
items = [
    {"id": 1, "name": "Laptop", "price": 12000000},
    {"id": 2, "name": "Mouse", "price": 150000},
    {"id": 3, "name": "Keyboard", "price": 350000},
]


@app.on_event("startup")
async def register_to_discovery():
    """Register diri ke service discovery saat startup."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{DISCOVERY_URL}/register",
                json={
                    "service_name": SERVICE_NAME,
                    "host": HOST,
                    "port": PORT,
                    "weight": 1,
                },
                timeout=5.0,
            )
            print(f"[{SERVICE_NAME}] Berhasil register ke discovery")
    except Exception as e:
        print(f"[{SERVICE_NAME}] Gagal register ke discovery: {e}")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()}


@app.get("/items")
async def get_items():
    return {"items": items, "total": len(items)}


@app.get("/items/{item_id}")
async def get_item(item_id: int):
    for item in items:
        if item["id"] == item_id:
            return {"item": item}
    return {"error": "Item not found"}


@app.post("/items")
async def create_item(item: dict):
    new_item = {"id": len(items) + 1, **item}
    items.append(new_item)
    return {"item": new_item, "message": "Item created"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
