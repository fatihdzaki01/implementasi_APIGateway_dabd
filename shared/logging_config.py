"""
Structured logging configuration.
Dipakai gateway middleware untuk mencatat setiap request/response.
Dikelola: Orang 5 (shared).
"""

import logging
import json
import sys
import time
import uuid
from datetime import datetime
from typing import Optional, Callable
from fastapi import Request
from fastapi.responses import Response, JSONResponse
from shared.schemas import RequestLog


# ============================================================
# JSON formatter — supaya log bisa di-parse Elasticsearch/Loki/dll
# ============================================================

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # tambahkan extra fields kalau ada
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """
    Buat logger dengan JSON formatter.
    Contoh:
        logger = get_logger("gateway")
        logger.info("Request received", extra={"path": "/service-a/items"})
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ============================================================
# Helper: log request ke stdout (dan opsional simpan ke DB)
# ============================================================

async def log_request(log: RequestLog, db=None) -> None:
    """
    Catat request log ke stdout sebagai JSON.
    Jika db disediakan, juga simpan ke tabel request_logs.

    Args:
        log: RequestLog schema (dari shared/schemas.py)
        db:  SQLAlchemy session (optional)
    """
    logger = get_logger("gateway.access")
    logger.info("request", extra=log.model_dump())

    if db is not None:
        try:
            from shared.models import RequestLog as RequestLogModel
            db_log = RequestLogModel(
                request_id=log.request_id,
                timestamp=log.timestamp,
                method=log.method,
                path=log.path,
                target_service=log.target_service,
                status_code=log.status_code,
                response_time_ms=log.response_time_ms,
                user_id=log.user_id,
                ip_address=log.ip_address,
            )
            db.add(db_log)
            db.commit()
        except Exception as e:
            logger.error(f"Gagal simpan request log ke DB: {e}")
            db.rollback()


# ============================================================
# Middleware: logging middleware untuk gateway pipeline
# Signature sesuai kontrak: async def middleware(request, call_next)
# ============================================================

async def logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Middleware logging — catat setiap request masuk ke gateway.
    Assign request_id, hitung response time, log hasilnya.
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()

    response = await call_next(request)

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    user_obj = getattr(request.state, "user", None)
    user_id_val = str(user_obj.id) if user_obj is not None else None

    log = RequestLog(
        request_id=request_id,
        timestamp=datetime.utcnow(),
        method=request.method,
        path=str(request.url.path),
        target_service=None,
        status_code=response.status_code,
        response_time_ms=elapsed_ms,
        user_id=user_id_val,
        ip_address=request.client.host if request.client else "unknown",
    )

    logger = get_logger("gateway.access")
    logger.info("request", extra=log.model_dump())

    return response
