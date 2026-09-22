"""
Configuration Module for Security
Orang 4 - Security Module

Centralized configuration management dengan environment variables.
"""

import os
from typing import Optional


class SecurityConfig:
    """
    Security module configuration.
    
    Semua config diambil dari environment variables dengan fallback ke default values.
    Untuk production, set environment variables di docker-compose atau .env file.
    """
    
    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY") or os.getenv("JWT_SECRET") or "dev-secret-key-CHANGE-IN-PRODUCTION"
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_MINUTES: int = int(os.getenv("JWT_EXPIRATION_MINUTES", "30"))
    
    # Rate Limiting Configuration
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    
    # Redis Configuration (optional, untuk production)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    USE_REDIS_RATE_LIMITER: bool = os.getenv("USE_REDIS_RATE_LIMITER", "false").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate configuration.
        Raise ValueError jika ada config yang invalid.
        """
        if cls.JWT_SECRET_KEY == "dev-secret-key-CHANGE-IN-PRODUCTION":
            import warnings
            warnings.warn(
                "WARNING: Using default JWT_SECRET_KEY! "
                "Set JWT_SECRET_KEY environment variable for production!",
                RuntimeWarning
            )
        
        if cls.JWT_EXPIRATION_MINUTES < 1:
            raise ValueError("JWT_EXPIRATION_MINUTES must be >= 1")
        
        if cls.RATE_LIMIT_MAX_REQUESTS < 1:
            raise ValueError("RATE_LIMIT_MAX_REQUESTS must be >= 1")
        
        if cls.RATE_LIMIT_WINDOW_SECONDS < 1:
            raise ValueError("RATE_LIMIT_WINDOW_SECONDS must be >= 1")


# Global config instance
config = SecurityConfig()

# Validate on import
config.validate()
