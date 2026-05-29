"""Rate limiting for Firebase Functions HTTP endpoints.

Provides simple in-memory rate limiting for API protection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional


@dataclass
class RateLimitEntry:
    """Rate limit tracking entry."""
    count: int = 0
    window_start: float = field(default_factory=time.time)
    
    def reset(self) -> None:
        """Reset the entry."""
        self.count = 0
        self.window_start = time.time()


class RateLimiter:
    """Simple in-memory rate limiter.
    
    Uses sliding window algorithm with configurable limits.
    """
    
    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        cleanup_interval: int = 300,
    ):
        """Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window per client
            window_seconds: Time window in seconds
            cleanup_interval: How often to clean old entries (seconds)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval
        
        self._entries: dict[str, RateLimitEntry] = {}
        self._lock = Lock()
        self._last_cleanup = time.time()
    
    def is_allowed(self, client_id: str) -> tuple[bool, dict]:
        """Check if request is allowed and increment counter.
        
        Args:
            client_id: Unique client identifier (e.g., IP + endpoint)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        
        with self._lock:
            # Periodic cleanup
            if now - self._last_cleanup > self.cleanup_interval:
                self._cleanup_old_entries(now)
            
            # Get or create entry
            entry = self._entries.get(client_id)
            if entry is None:
                entry = RateLimitEntry()
                self._entries[client_id] = entry
            
            # Check if window expired
            if now - entry.window_start > self.window_seconds:
                entry.reset()
            
            # Check limit
            if entry.count >= self.max_requests:
                reset_time = entry.window_start + self.window_seconds
                remaining = max(0, int(reset_time - now))
                
                return False, {
                    "allowed": False,
                    "limit": self.max_requests,
                    "remaining": 0,
                    "reset_after_seconds": remaining,
                }
            
            # Allow request and increment
            entry.count += 1
            remaining = self.max_requests - entry.count
            
            return True, {
                "allowed": True,
                "limit": self.max_requests,
                "remaining": remaining,
                "reset_after_seconds": int(self.window_seconds - (now - entry.window_start)),
            }
    
    def _cleanup_old_entries(self, now: float) -> None:
        """Remove expired entries."""
        expired = [
            key for key, entry in self._entries.items()
            if now - entry.window_start > self.window_seconds * 2
        ]
        for key in expired:
            del self._entries[key]
        
        self._last_cleanup = now
    
    def get_status(self, client_id: str) -> dict:
        """Get current rate limit status without incrementing.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Rate limit status
        """
        now = time.time()
        
        with self._lock:
            entry = self._entries.get(client_id)
            if entry is None:
                return {
                    "limit": self.max_requests,
                    "remaining": self.max_requests,
                    "reset_after_seconds": self.window_seconds,
                }
            
            # Check if window expired
            if now - entry.window_start > self.window_seconds:
                return {
                    "limit": self.max_requests,
                    "remaining": self.max_requests,
                    "reset_after_seconds": self.window_seconds,
                }
            
            remaining = max(0, self.max_requests - entry.count)
            return {
                "limit": self.max_requests,
                "remaining": remaining,
                "reset_after_seconds": int(self.window_seconds - (now - entry.window_start)),
            }


# Global rate limiter instance
# Per-endpoint: 10 requests per minute
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
    return _rate_limiter


def check_rate_limit(client_ip: str, endpoint: str) -> tuple[bool, Optional[dict]]:
    """Check rate limit for a client.
    
    Args:
        client_ip: Client IP address
        endpoint: Endpoint name (e.g., "run_now")
        
    Returns:
        Tuple of (is_allowed, rate_limit_info or None if blocked)
    """
    client_id = f"{client_ip}:{endpoint}"
    limiter = get_rate_limiter()
    
    is_allowed, info = limiter.is_allowed(client_id)
    
    if not is_allowed:
        return False, info
    
    return True, None


def get_client_ip(request) -> str:
    """Extract client IP from request.
    
    Handles various proxy headers and falls back to remote address.
    
    Args:
        request: Flask/Firebase request object
        
    Returns:
        Client IP address
    """
    # Check X-Forwarded-For header (common for proxies)
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # Take the first IP in the chain
        return forwarded.split(",")[0].strip()
    
    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-Ip", "")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to remote address
    if hasattr(request, 'remote_addr') and request.remote_addr:
        return request.remote_addr
    
    return "unknown"
