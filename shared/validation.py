"""
Request validation middleware menggunakan Pydantic.
Di-plug ke gateway middleware pipeline oleh Orang 5.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Callable, Optional, Type
from pydantic import BaseModel, ValidationError
import json


# ============================================================
# Helper: validasi request body terhadap Pydantic schema
# ============================================================

async def validate_body(request: Request, schema: Type[BaseModel]) -> Optional[BaseModel]:
    """
    Parse dan validasi JSON body request ke Pydantic schema.
    Return instance schema jika valid, raise ValueError jika tidak.

    Contoh:
        body = await validate_body(request, CreateItemRequest)
    """
    try:
        raw = await request.json()
        return schema(**raw)
    except json.JSONDecodeError:
        raise ValueError("Request body bukan JSON yang valid")
    except ValidationError as e:
        raise ValueError(str(e))


# ============================================================
# Middleware: validation middleware untuk pipeline gateway
# Signature sesuai kontrak: async def middleware(request, call_next)
# ============================================================

async def validation_middleware(request: Request, call_next: Callable):
    """
    Middleware validasi — saat ini hanya memastikan Content-Type JSON
    untuk request yang punya body (POST, PUT, PATCH).
    Orang 5 bisa extend dengan schema validation per-route di sini.
    """
    if request.method in ("POST", "PUT", "PATCH"):
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type:
            return JSONResponse(
                status_code=415,
                content={
                    "success": False,
                    "error": "Content-Type harus application/json",
                    "request_id": None,
                    "data": None,
                }
            )
    return await call_next(request)
