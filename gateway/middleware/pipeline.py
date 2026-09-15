"""
Middleware pipeline manager.
Orang 1 (gateway) yang maintain file ini.

Cara kerja:
    1. Modul lain memanggil register_middleware(fn) saat startup.
    2. Saat ada request masuk, run_pipeline() menjalankan semua middleware
       yang terdaftar secara berurutan (chain of responsibility pattern).

Urutan middleware default (diatur di gateway/main.py):
    1. logging_middleware    (Orang 5)
    2. auth_middleware       (Orang 4)
    3. rate_limit_middleware (Orang 4)
    4. validation_middleware (Orang 5)
"""

from fastapi import Request
from fastapi.responses import Response
from typing import Callable, Awaitable

# Type alias — kontrak signature untuk semua middleware
MiddlewareFunc = Callable[[Request, Callable], Awaitable[Response]]

# Registry middleware yang aktif (diisi saat startup via register_middleware)
_middlewares: list[MiddlewareFunc] = []


def register_middleware(fn: MiddlewareFunc) -> None:
    """
    Daftarkan middleware ke pipeline.
    Panggil di gateway/main.py pada saat startup:

        from gateway.middleware.pipeline import register_middleware
        from security.auth import auth_middleware
        register_middleware(auth_middleware)
    """
    _middlewares.append(fn)


def get_middlewares() -> list[MiddlewareFunc]:
    """Return daftar middleware yang terdaftar (untuk debugging)."""
    return list(_middlewares)


async def run_pipeline(request: Request, final_handler: Callable) -> Response:
    """
    Jalankan semua middleware terdaftar secara berantai, lalu panggil final_handler.

    Pattern: middleware[0] → middleware[1] → ... → final_handler

    Args:
        request:       FastAPI Request object
        final_handler: Fungsi async yang melakukan reverse proxy ke service backend
    """
    # Bangun chain dari belakang ke depan
    handler = final_handler
    for middleware in reversed(_middlewares):
        # capture middleware di closure
        _mw = middleware
        _next = handler

        async def make_next(mw=_mw, nxt=_next):
            async def chained(req: Request) -> Response:
                return await mw(req, nxt)
            return chained

        handler = (await make_next())

    return await handler(request)
