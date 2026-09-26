from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from shared.models import User, Role, ApiKey
from shared.schemas import TokenPayload

from security.config import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user: User) -> tuple[str, int]:
    expires_delta = timedelta(minutes=config.JWT_EXPIRATION_MINUTES)
    expire = datetime.utcnow() + expires_delta

    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.name if user.role else "user",
        "exp": int(expire.timestamp()),
        "iat": int(datetime.utcnow().timestamp())
    }

    token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    expires_in = int(expires_delta.total_seconds())

    return token, expires_in


def decode_access_token(token: str) -> Optional[TokenPayload]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])

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


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None

    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def create_user(db: Session, username: str, password: str, role_id: Optional[int] = None) -> User:
    password_hash = hash_password(password)

    if role_id is None:
        default_role = db.query(Role).filter(Role.name == "user").first()
        role_id = default_role.id if default_role else None

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


def check_permission(user: User, method: str, path: str) -> bool:
    if not user or not user.role:
        return False

    permissions = user.role.permissions or {}

    permission_key = f"{method} {path}"
    if permission_key in permissions:
        return permissions[permission_key]

    for perm_pattern, allowed in permissions.items():
        if not allowed:
            continue

        if " " not in perm_pattern:
            continue

        perm_method, perm_path = perm_pattern.split(" ", 1)

        if perm_method != "*" and perm_method != method:
            continue

        if perm_path == "*":
            return True
        elif perm_path.endswith("/*"):
            prefix = perm_path[:-2]
            if path.startswith(prefix):
                return True
        elif perm_path.endswith("*"):
            prefix = perm_path[:-1]
            if not prefix or path.startswith(prefix):
                return True
        elif perm_path == path:
            return True

    return False


def is_admin(user: User) -> bool:
    return user and user.role and user.role.name == "admin"


import hashlib
import secrets


def generate_api_key() -> str:
    return f"gw_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def create_user_api_key(
    db: Session,
    user_id: int,
    description: Optional[str] = None,
    expires_at: Optional[datetime] = None
) -> tuple[ApiKey, str]:
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
    key_hash = hash_api_key(api_key)

    api_key_obj = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True
    ).first()

    if not api_key_obj:
        return None

    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
        return None

    user = db.query(User).filter(
        User.id == api_key_obj.user_id,
        User.is_active == True
    ).first()

    return user
