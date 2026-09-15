"""
ORM Models — definisi tabel database.
Semua tabel dikelola di sini supaya migration konsisten.
File ini di-maintain oleh Orang 4 (tabel users/roles/api_keys) dan Orang 5 (tabel request_logs).
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Text, Boolean, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from datetime import datetime
import uuid

from shared.db import Base


# ============================================================
# Tabel: roles
# Dikelola: Orang 4 (security)
# ============================================================

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)    # e.g. "admin", "user", "readonly"
    permissions = Column(JSON, default={})                    # {"GET /service-a/*": True, ...}
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="role")


# ============================================================
# Tabel: users
# Dikelola: Orang 4 (security)
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)              # bcrypt hash
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("Role", back_populates="users")
    api_keys = relationship("ApiKey", back_populates="user")
    request_logs = relationship("RequestLog", back_populates="user")


# ============================================================
# Tabel: api_keys
# Dikelola: Orang 4 (security)
# ============================================================

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(Text, unique=True, nullable=False)      # hash dari API key (jangan simpan plain)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)              # None = tidak expire
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")


# ============================================================
# Tabel: request_logs
# Dikelola: Orang 5 (shared)
# ============================================================

class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(36), nullable=False, index=True)   # UUID string
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    method = Column(String(10), nullable=False)                   # GET, POST, ...
    path = Column(Text, nullable=False)                           # /service-a/items
    target_service = Column(String(100), nullable=True)           # "service-a"
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(50), nullable=True)

    user = relationship("User", back_populates="request_logs")
