import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import httpx
import os

app = FastAPI(title="Service A", version="1.0.0")

SERVICE_NAME = "service-a"
HOST = os.getenv("SERVICE_HOST", "service-a")
PORT = int(os.getenv("SERVICE_PORT", "8001"))
DISCOVERY_URL = os.getenv("DISCOVERY_URL", "http://discovery-lb:8010")

INSTANCE_ID = f"{SERVICE_NAME}_{HOST}_{PORT}"

items = [
    {"id": 1, "name": "Laptop", "price": 12000000},
    {"id": 2, "name": "Mouse", "price": 150000},
    {"id": 3, "name": "Keyboard", "price": 350000},
]


class ItemCreate(BaseModel):
    name: str
    price: float


@app.on_event("startup")
async def register_to_discovery():
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
            except Exception:
                pass
            print(f"[{SERVICE_NAME}] Retry register ({attempt}/10)...")
            await asyncio.sleep(3)
        print(f"[{SERVICE_NAME}] Gagal register setelah 10 percobaan")
        return False

    await _register_with_retry()

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


@app.get("/items")
async def get_items():
    return {"items": items, "total": len(items)}


@app.get("/items/{item_id}")
async def get_item(item_id: int):
    for item in items:
        if item["id"] == item_id:
            return {"item": item}
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/items")
async def create_item(item: ItemCreate):
    new_item = {"id": len(items) + 1, "name": item.name, "price": item.price}
    items.append(new_item)
    return {"item": new_item, "message": "Item created"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
