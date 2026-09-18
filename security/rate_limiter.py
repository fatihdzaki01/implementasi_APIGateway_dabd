"""
Rate Limiter Implementation
Orang 4 - Security Module

Implementasi sliding window rate limiter menggunakan in-memory store.
Untuk production, bisa diganti dengan Redis.
"""

import time
from typing import Dict, List, Tuple
from collections import defaultdict
import threading


class RateLimiter:
    """
    Sliding window rate limiter.
    
    Tracks request timestamps per identifier (user_id atau IP).
    Default: 100 requests per 60 seconds.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        # Store: {identifier: [timestamp1, timestamp2, ...]}
        self._store: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def _clean_old_entries(self, identifier: str, current_time: float) -> None:
        """Remove timestamps outside the current window."""
        window_start = current_time - self.window_seconds
        self._store[identifier] = [
            ts for ts in self._store[identifier]
            if ts > window_start
        ]
    
    def check_rate_limit(self, identifier: str) -> Tuple[bool, int, float]:
        """
        Check if request is within rate limit.
        
        Args:
            identifier: Unique identifier (e.g. "user:123" atau "ip:192.168.1.1")
        
        Returns:
            tuple: (is_allowed, remaining_requests, reset_timestamp)
        """
        with self._lock:
            current_time = time.time()
            
            # Clean old entries
            self._clean_old_entries(identifier, current_time)
            
            # Check current count
            current_count = len(self._store[identifier])
            
            if current_count >= self.max_requests:
                # Rate limit exceeded
                # Calculate reset time (oldest request + window)
                if self._store[identifier]:
                    oldest = self._store[identifier][0]
                    reset_time = oldest + self.window_seconds
                else:
                    reset_time = current_time + self.window_seconds
                
                return False, 0, reset_time
            
            # Add current request
            self._store[identifier].append(current_time)
            
            remaining = self.max_requests - (current_count + 1)
            reset_time = current_time + self.window_seconds
            
            return True, remaining, reset_time
    
    def reset(self, identifier: str) -> None:
        """Reset rate limit for specific identifier."""
        with self._lock:
            if identifier in self._store:
                del self._store[identifier]
    
    def reset_all(self) -> None:
        """Reset all rate limits (untuk testing)."""
        with self._lock:
            self._store.clear()
    
    def get_current_count(self, identifier: str) -> int:
        """Get current request count for identifier."""
        with self._lock:
            current_time = time.time()
            self._clean_old_entries(identifier, current_time)
            return len(self._store[identifier])


# ============================================================
# Redis-based Rate Limiter (Alternative - untuk production)
# ============================================================

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisRateLimiter:
    """
    Redis-based rate limiter for distributed systems.
    Gunakan ini untuk production dengan multiple gateway instances.
    """
    
    def __init__(
        self, 
        redis_host: str = "localhost",
        redis_port: int = 6379,
        max_requests: int = 100,
        window_seconds: int = 60
    ):
        if not REDIS_AVAILABLE:
            raise ImportError("redis package not installed. Run: pip install redis")
        
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    def check_rate_limit(self, identifier: str) -> Tuple[bool, int, float]:
        """
        Check rate limit menggunakan Redis ZSET.
        
        Returns:
            tuple: (is_allowed, remaining_requests, reset_timestamp)
        """
        key = f"rate_limit:{identifier}"
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        # Remove old entries
        self.redis_client.zremrangebyscore(key, 0, window_start)
        
        # Get current count
        current_count = self.redis_client.zcard(key)
        
        if current_count >= self.max_requests:
            # Rate limit exceeded
            oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
            reset_time = oldest[0][1] + self.window_seconds if oldest else current_time + self.window_seconds
            return False, 0, reset_time
        
        # Add current request
        self.redis_client.zadd(key, {str(current_time): current_time})
        
        # Set expiration
        self.redis_client.expire(key, self.window_seconds)
        
        remaining = self.max_requests - (current_count + 1)
        reset_time = current_time + self.window_seconds
        
        return True, remaining, reset_time
    
    def reset(self, identifier: str) -> None:
        """Reset rate limit for specific identifier."""
        key = f"rate_limit:{identifier}"
        self.redis_client.delete(key)
    
    def get_current_count(self, identifier: str) -> int:
        """Get current request count for identifier."""
        key = f"rate_limit:{identifier}"
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        self.redis_client.zremrangebyscore(key, 0, window_start)
        return self.redis_client.zcard(key)
