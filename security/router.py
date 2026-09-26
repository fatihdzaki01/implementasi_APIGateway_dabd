from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from shared.db import get_db
from shared.models import User, Role
from shared.schemas import LoginRequest, LoginResponse

from security.auth import (
    authenticate_user, create_access_token, create_user,
    create_user_api_key, hash_password
)
from security.dependencies import get_current_user
from security.config import config

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    role_name: Optional[str] = Field(default="user")


class UserResponse(BaseModel):
    id: int
    username: str
    role: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyResponse(BaseModel):
    api_key: str
    description: Optional[str]
    expires_at: Optional[datetime]
    message: str = "Save this API key securely. It won't be shown again."


class ApiKeyRequest(BaseModel):
    description: Optional[str] = None
    expires_in_days: Optional[int] = Field(None, gt=0, le=365)


router = APIRouter(prefix="/auth", tags=["Authentication"])

bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    role = db.query(Role).filter(Role.name == request.role_name).first()
    if not role:
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
    user = authenticate_user(db, request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_in = create_access_token(user)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
    _: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
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
    _: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    expires_at = None
    if request.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

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
    return {"status": "healthy", "service": "auth"}


@router.post("/rate-limit/reset")
async def reset_rate_limit(
    user: User = Depends(get_current_user),
    _: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    from security.middleware import rate_limiter
    identifier = f"user:{user.id}"
    rate_limiter.reset(identifier)
    return {
        "message": f"Rate limit counter reset untuk {identifier}",
        "identifier": identifier,
        "max_requests": rate_limiter.max_requests,
        "window_seconds": rate_limiter.window_seconds
    }
