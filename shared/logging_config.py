"""
Structured logging configuration.
Dipakai gateway middleware untuk mencatat setiap request/response.
Dikelola: Orang 5 (shared).
"""

import logging
import json
import sys
from datetime import datetime
from typing import Optional
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
