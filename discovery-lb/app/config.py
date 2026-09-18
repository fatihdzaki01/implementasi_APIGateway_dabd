import os

class Settings:
    HEARTBEAT_TTL_SECONDS: int = int(os.getenv("HEARTBEAT_TTL_SECONDS", "15"))
    CLEANUP_INTERVAL_SECONDS: int = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "5"))
    DEFAULT_STRATEGY: str = os.getenv("DEFAULT_STRATEGY", "round_robin")
    REGISTRY_BACKEND: str = os.getenv("REGISTRY_BACKEND", "in_memory")  # "in_memory" or "redis"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

settings = Settings()
