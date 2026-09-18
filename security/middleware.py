"""
Security Middleware untuk Gateway
Orang 4 - Security Module

Middleware yang akan di-register ke gateway/middleware/pipeline.py:
- auth_middleware: Authentication & Authorization check
- rate_limit_middleware: Rate limiting per user/IP

WAJIB ikuti signature: async def middleware(request: Request, call_next: Callable) -> Response
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from typing import Callable
import uuid

# Import dari shared (kontrak)
from shared.db import SessionLocal
from shared.schemas import StandardResponse

# Import dari security module
from security.auth import decode_access_token, get_user_by_id, check_permission, verify_api_key
from security.rate_limiter import RateLimiter
from security.config import config

# Global rate limiter instance
rate_limiter = RateLimiter(
    max_requests=config.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=config.RATE_LIMIT_WINDOW_SECONDS
)


# ============================================================
# Helper Functions
# ============================================================

def create_error_response(
    status_code: int,
    error_message: str,
    request_id: str
) -> JSONResponse:
    """Create standardized error response."""
    response_data = StandardResponse(
        success=False,
        data=None,
        error=error_message,
        request_id=request_id
    )
    return JSONResponse(
        status_code=status_code,
        content=response_data.dict()
    )


def get_request_id(request: Request) -> str:
    """Get or create request ID."""
    # Check if request_id already set by logging middleware
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    return str(uuid.uuid4())


# ============================================================
# Auth Middleware
# ============================================================

async def auth_middleware(request: Request, call_next: Callable) -> Response:
    """
    Authentication & Authorization Middleware.
    
    Flow:
    1. Extract token dari Authorization header atau API key dari X-API-Key header
    2. Verify token/key dan get user
    3. Inject user ke request.state.user
    4. Check authorization (role-based permission)
    5. Call next middleware/handler
    
    Public endpoints (tidak perlu auth):
    - /health
    - /status
    - /auth/login
    - /auth/register
    - /docs, /redoc, /openapi.json
    """
    
    # Get request ID
    request_id = get_request_id(request)
    request.state.request_id = request_id
    
    # Check if endpoint is public (skip auth)
    public_paths = ["/health", "/status", "/auth/login", "/auth/register", 
                   "/docs", "/redoc", "/openapi.json"]
    
    if any(request.url.path.startswith(path) for path in public_paths):
        return await call_next(request)
    
    # Try to authenticate
    db = SessionLocal()
    user = None
    
    try:
        # Method 1: JWT Token (Authorization: Bearer <token>)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer "
            token_payload = decode_access_token(token)
            
            if token_payload:
                user = get_user_by_id(db, int(token_payload.user_id))
        
        # Method 2: API Key (X-API-Key: <key>)
        if not user:
            api_key = request.headers.get("X-API-Key")
            if api_key:
                user = verify_api_key(db, api_key)
        
        # If no valid authentication
        if not user:
            db.close()
            return create_error_response(
                status_code=401,
                error_message="Authentication required. Provide valid JWT token or API key.",
                request_id=request_id
            )
        
        # Inject user to request state
        request.state.user = user
        request.state.user_id = str(user.id)
        
        # Check authorization (RBAC)
        method = request.method
        path = request.url.path
        
        if not check_permission(user, method, path):
            db.close()
            return create_error_response(
                status_code=403,
                error_message=f"Access denied. User role '{user.role.name if user.role else 'none'}' not authorized for {method} {path}.",
                request_id=request_id
            )
        
        # Auth & authz successful, proceed
        response = await call_next(request)
        
        return response
        
    except Exception as e:
        return create_error_response(
            status_code=500,
            error_message=f"Authentication error: {str(e)}",
            request_id=request_id
        )
    finally:
        db.close()


# ============================================================
# Rate Limit Middleware
# ============================================================

async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """
    Rate Limiting Middleware.
    
    Limit requests per user (jika authenticated) atau per IP (jika anonymous).
    Default: 100 requests per minute.
    
    Response headers:
    - X-RateLimit-Limit: max requests
    - X-RateLimit-Remaining: remaining requests
    - X-RateLimit-Reset: timestamp when limit resets
    """
    
    # Get request ID
    request_id = get_request_id(request)
    
    # Skip rate limiting untuk health check
    if request.url.path in ["/health", "/status"]:
        return await call_next(request)
    
    # Determine identifier (user_id or IP)
    identifier = None
    
    # Try to use user_id if authenticated
    if hasattr(request.state, "user_id"):
        identifier = f"user:{request.state.user_id}"
    else:
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        # Check for X-Forwarded-For header (if behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        identifier = f"ip:{client_ip}"
    
    # Check rate limit
    allowed, remaining, reset_time = rate_limiter.check_rate_limit(identifier)
    
    if not allowed:
        # Rate limit exceeded
        response = create_error_response(
            status_code=429,
            error_message="Rate limit exceeded. Please try again later.",
            request_id=request_id
        )
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        response.headers["Retry-After"] = str(rate_limiter.window_seconds)
        return response
    
    # Proceed with request
    response = await call_next(request)
    
    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(reset_time))
    
    return response
