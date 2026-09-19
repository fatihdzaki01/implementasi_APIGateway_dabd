"""
Dummy Service C — Users service
Port: 8003
"""

import asyncio
from fastapi import FastAPI
from datetime import datetime
import httpx
import os

app = FastAPI(title="Service C", version="1.0.0")

SERVICE_NAME = "service-c"
HOST = os.getenv("SERVICE_HOST", "service-c")
PORT = int(os.getenv("SERVICE_PORT", "8003"))
DISCOVERY_URL = os.getenv("DISCOVERY_URL", "http://discovery-lb:8010")

INSTANCE_ID = f"{SERVICE_NAME}_{HOST}_{PORT}"

# In-memory dummy data
users = [
    {"id": 1, "name": "Budi Santoso", "email": "budi@example.com", "role": "admin"},
    {"id": 2, "name": "Siti Rahayu", "email": "siti@example.com", "role": "user"},
    {"id": 3, "name": "Andi Wijaya", "email": "andi@example.com", "role": "readonly"},
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


@app.get("/users")
async def get_users():
    return {"users": users, "total": len(users)}


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    for user in users:
        if user["id"] == user_id:
            return {"user": user}
    return {"error": "User not found"}


@app.post("/users")
async def create_user(user: dict):
    new_user = {"id": len(users) + 1, **user}
    users.append(new_user)
    return {"user": new_user, "message": "User created"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
