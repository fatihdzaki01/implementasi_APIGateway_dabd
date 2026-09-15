"""
Auth Router - Endpoints untuk Authentication
Orang 4 - Security Module

Endpoints:
- POST /auth/register - Register user baru
- POST /auth/login - Login dan dapatkan JWT token
- POST /auth/api-key - Generate API key (requires authentication)
- GET /auth/me - Get current user info
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import dari shared (kontrak)
from shared.db import get_db
from shared.models import User, Role
from shared.schemas import LoginRequest, LoginResponse

# Import dari security module
from security.auth import (
    authenticate_user, create_access_token, create_user,
    create_user_api_key, hash_password
)
from security.dependencies import get_current_user
from security.config import config

# Pydantic models untuk request/response
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ============================================================
# Schemas
# ============================================================

class RegisterRequest(BaseModel):
    """Request body untuk register."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    role_name: Optional[str] = Field(default="user", description="Role: admin, user, readonly")


class UserResponse(BaseModel):
    """Response untuk user info."""
    id: int
    username: str
    role: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ApiKeyResponse(BaseModel):
    """Response untuk API key creation."""
    api_key: str
    description: Optional[str]
    expires_at: Optional[datetime]
    message: str = "Save this API key securely. It won't be shown again."


class ApiKeyRequest(BaseModel):
    """Request untuk create API key."""
    description: Optional[str] = None
    expires_in_days: Optional[int] = Field(None, gt=0, le=365)


# ============================================================
# Router
# ============================================================

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register user baru.
    
    Default role: 'user'
    Untuk create admin, gunakan role_name: 'admin' (hanya bisa dilakukan via DB atau admin endpoint)
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Get role
    role = db.query(Role).filter(Role.name == request.role_name).first()
    if not role:
        # Create default user role if not exists
        if request.role_name == "user":
            role = Role(
                name="user",
                permissions={
                    "GET /service-a/*": True,
                    "GET /service-b/*": True,
                    "GET /service-c/*": True,
                    "POST /service-a/items": True
                }
            )
            db.add(role)
            db.commit()
            db.refresh(role)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{request.role_name}' not found"
            )
    
    # Create user
    user = create_user(
        db=db,
        username=request.username,
        password=request.password,
        role_id=role.id
    )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role.name if user.role else None,
        is_active=user.is_active,
        created_at=user.created_at
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login dengan username & password.
    
    Returns JWT token yang bisa dipakai untuk authenticated requests.
    """
    # Authenticate user
    user = authenticate_user(db, request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token, expires_in = create_access_token(user)
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user)
):
    """
    Get current authenticated user info.
    
    Requires: Authorization header dengan valid JWT token
    """
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role.name if user.role else None,
        is_active=user.is_active,
        created_at=user.created_at
    )


@router.post("/api-key", response_model=ApiKeyResponse)
async def create_api_key(
    request: ApiKeyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate API key untuk current user.
    
    Requires: Authentication (JWT token)
    
    API key bisa digunakan sebagai alternatif JWT token.
    Gunakan header: X-API-Key: <your-api-key>
    """
    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    # Create API key
    api_key_obj, plain_key = create_user_api_key(
        db=db,
        user_id=user.id,
        description=request.description,
        expires_at=expires_at
    )
    
    return ApiKeyResponse(
        api_key=plain_key,
        description=api_key_obj.description,
        expires_at=api_key_obj.expires_at
    )


@router.get("/health")
async def health_check():
    """Health check untuk auth service."""
    return {"status": "healthy", "service": "auth"}
