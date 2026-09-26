import os
from datetime import datetime
from fastapi import FastAPI, Response

app = FastAPI(title="Stub Service (Resilience Testing)")

_healthy = True
SERVICE_NAME = os.getenv("SERVICE_NAME", "stub-service")


@app.get("/health")
def health(response: Response):
    if _healthy:
        return {"status": "healthy", "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()}
    else:
        response.status_code = 503
        return {"status": "unhealthy", "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()}


@app.get("/break")
def break_service():
    global _healthy
    _healthy = False
    return {"message": f"[{SERVICE_NAME}] Service sekarang SAKIT (health → 503)"}


@app.get("/recover")
def recover_service():
    global _healthy
    _healthy = True
    return {"message": f"[{SERVICE_NAME}] Service sekarang SEHAT (health → 200)"}


@app.get("/")
def root():
    return {"service": SERVICE_NAME, "healthy": _healthy}
