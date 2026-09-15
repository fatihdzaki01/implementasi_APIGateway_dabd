"""
FastAPI Dependencies untuk Security
Orang 4 - Security Module

Dependencies yang bisa dipakai di router endpoints:
- get_current_user: Get authenticated user dari request
- require_role: Decorator untuk role-based access
"""

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional

# Import dari shared
import sys
sys.path.append('..')
from shared.db import get_db
from shared.models import User


# ============================================================
# Current User Dependency
# ============================================================

def get_current_user(request: Request) -> User:
    """
    FastAPI dependency untuk mendapatkan current authenticated user.
    
    Usage:
        @router.get("/profile")
        async def get_profile(user: User = Depends(get_current_user)):
            return {"username": user.username}
    
    Raises:
        HTTPException 401: Jika user tidak authenticated
    """
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return request.state.user


def get_current_user_optional(request: Request) -> Optional[User]:
    """
    FastAPI dependency untuk mendapatkan current user (optional).
    Return None jika tidak authenticated.
    
    Usage:
        @router.get("/public")
        async def public_endpoint(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user.username}"}
            return {"message": "Hello guest"}
    """
    if hasattr(request.state, "user"):
        return request.state.user
    return None


# ============================================================
# Role-Based Dependencies
# ============================================================

def require_role(required_role: str):
    """
    Dependency factory untuk role-based access control.
    
    Usage:
        @router.post("/admin/users")
        async def create_user(user: User = Depends(require_role("admin"))):
            # Only admin can access this
            pass
    
    Args:
        required_role: Role name yang dibutuhkan (e.g. "admin", "user")
    
    Returns:
        Dependency function
    """
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if not user.role or user.role.name != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role}"
            )
        return user
    
    return role_checker


def require_any_role(*roles: str):
    """
    Dependency factory untuk multiple role check.
    User harus memiliki salah satu dari role yang disebutkan.
    
    Usage:
        @router.get("/data")
        async def get_data(user: User = Depends(require_any_role("admin", "user"))):
            # Admin atau user bisa access
            pass
    
    Args:
        *roles: Variable number of role names
    
    Returns:
        Dependency function
    """
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if not user.role or user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required one of: {', '.join(roles)}"
            )
        return user
    
    return role_checker


def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Dependency untuk admin-only endpoints.
    Shortcut untuk require_role("admin").
    
    Usage:
        @router.delete("/users/{user_id}")
        async def delete_user(
            user_id: int,
            admin: User = Depends(require_admin)
        ):
            # Only admin can delete users
            pass
    """
    if not user.role or user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


# ============================================================
# Active User Check
# ============================================================

def get_active_user(user: User = Depends(get_current_user)) -> User:
    """
    Dependency untuk memastikan user aktif.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_active_user)):
            # User pasti active
            pass
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    return user
