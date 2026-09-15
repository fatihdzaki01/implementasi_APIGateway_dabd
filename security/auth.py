"""
Authentication & Authorization Logic
Orang 4 - Security Module

Fungsi-fungsi untuk:
- Password hashing & verification
- JWT token generation & verification
- Role-based permission check
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

# Import dari shared (kontrak yang sudah disepakati)
import sys
sys.path.append('..')
from shared.models import User, Role, ApiKey
from shared.schemas import TokenPayload

# Configuration
JWT_SECRET_KEY = "dev-secret-key-CHANGE-IN-PRODUCTION"  # TODO: move to env
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 30

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# Password Management
# ============================================================

def hash_password(password: str) -> str:
    """Hash password menggunakan bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password dengan hash-nya."""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# JWT Token Management
# ============================================================

def create_access_token(user: User) -> tuple[str, int]:
    """
    Buat JWT access token untuk user.
    
    Returns:
        tuple: (token_string, expires_in_seconds)
    """
    expires_delta = timedelta(minutes=JWT_EXPIRATION_MINUTES)
    expire = datetime.utcnow() + expires_delta
    
    # Payload sesuai shared.schemas.TokenPayload
    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.name if user.role else "user",
        "exp": int(expire.timestamp()),
        "iat": int(datetime.utcnow().timestamp())
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    expires_in = int(expires_delta.total_seconds())
    
    return token, expires_in


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """
    Decode dan verify JWT token.
    
    Returns:
        TokenPayload jika valid, None jika invalid/expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Validate payload structure
        if "user_id" not in payload or "username" not in payload or "role" not in payload:
            return None
        
        return TokenPayload(
            user_id=payload["user_id"],
            username=payload["username"],
            role=payload["role"],
            exp=payload["exp"]
        )
    except JWTError:
        return None


# ============================================================
# User Authentication
# ============================================================

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate user dengan username & password.
    
    Returns:
        User object jika valid, None jika invalid
    """
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        return None
    
    if not user.is_active:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def create_user(db: Session, username: str, password: str, role_id: Optional[int] = None) -> User:
    """
    Create new user.
    
    Args:
        db: Database session
        username: Username (unique)
        password: Plain password (akan di-hash)
        role_id: Role ID (optional, default ke role 'user')
    """
    # Hash password
    password_hash = hash_password(password)
    
    # Get default role if not specified
    if role_id is None:
        default_role = db.query(Role).filter(Role.name == "user").first()
        role_id = default_role.id if default_role else None
    
    # Create user
    user = User(
        username=username,
        password_hash=password_hash,
        role_id=role_id,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


# ============================================================
# Authorization (RBAC)
# ============================================================

def check_permission(user: User, method: str, path: str) -> bool:
    """
    Check apakah user memiliki permission untuk mengakses endpoint.
    
    Args:
        user: User object (harus sudah include .role relationship)
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: Request path (e.g. /service-a/items)
    
    Returns:
        True jika authorized, False jika tidak
    """
    if not user or not user.role:
        return False
    
    permissions = user.role.permissions or {}
    
    # Check exact match first
    permission_key = f"{method} {path}"
    if permission_key in permissions:
        return permissions[permission_key]
    
    # Check wildcard patterns
    # Format: "GET /service-a/*" -> allow all GET to /service-a/
    for perm_pattern, allowed in permissions.items():
        if not allowed:
            continue
        
        # Parse pattern
        if " " not in perm_pattern:
            continue
        
        perm_method, perm_path = perm_pattern.split(" ", 1)
        
        # Check method match
        if perm_method != "*" and perm_method != method:
            continue
        
        # Check path match with wildcard
        if perm_path.endswith("/*"):
            prefix = perm_path[:-2]  # Remove /*
            if path.startswith(prefix):
                return True
        elif perm_path == "*":
            return True
        elif perm_path == path:
            return True
    
    return False


def is_admin(user: User) -> bool:
    """Check jika user adalah admin."""
    return user and user.role and user.role.name == "admin"


# ============================================================
# API Key Management
# ============================================================

import hashlib
import secrets


def generate_api_key() -> str:
    """Generate random API key."""
    return f"gw_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash API key untuk disimpan di database."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def create_user_api_key(
    db: Session, 
    user_id: int, 
    description: Optional[str] = None,
    expires_at: Optional[datetime] = None
) -> tuple[ApiKey, str]:
    """
    Create API key untuk user.
    
    Returns:
        tuple: (ApiKey object, plain_key_string)
        Plain key hanya di-return sekali, tidak disimpan di DB!
    """
    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)
    
    api_key = ApiKey(
        key_hash=key_hash,
        user_id=user_id,
        description=description,
        expires_at=expires_at,
        is_active=True
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return api_key, plain_key


def verify_api_key(db: Session, api_key: str) -> Optional[User]:
    """
    Verify API key dan return user-nya.
    
    Returns:
        User object jika valid, None jika invalid/expired
    """
    key_hash = hash_api_key(api_key)
    
    api_key_obj = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True
    ).first()
    
    if not api_key_obj:
        return None
    
    # Check expiration
    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
        return None
    
    # Get user
    user = db.query(User).filter(
        User.id == api_key_obj.user_id,
        User.is_active == True
    ).first()
    
    return user
