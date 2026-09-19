"""
Security Service — FastAPI app entrypoint.
Orang 4 (security) yang maintain file ini.

Jalankan sendiri sebagai microservice, atau di-import oleh gateway.
"""

import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Pastikan parent directory ada di sys.path supaya import `shared` dan `security` jalan
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security.router import router as auth_router
from security.config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("  Security Service — Starting...")
    print("=" * 60)
    print(f"  JWT_SECRET  : {'(set)' if os.getenv('JWT_SECRET') else '(default)'}")
    print(f"  DATABASE_URL: {'(set)' if os.getenv('DATABASE_URL') else '(not set)'}")
    print("=" * 60)
    yield
    print("Security Service — Shutdown complete.")


app = FastAPI(
    title="Security Service",
    description="Authentication, Authorization, Rate Limiting",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "security"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8030)
