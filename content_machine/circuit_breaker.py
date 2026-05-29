"""Circuit breaker pattern for external API calls.

Prevents cascading failures when external services are down.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5           # Failures before opening
    recovery_timeout: float = 60.0       # Seconds before half-open
    half_open_max_calls: int = 3         # Test calls in half-open
    success_threshold: int = 2           # Successes to close
    

@dataclass
class CircuitBreaker:
    """Circuit breaker for external API calls."""
    name: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _success_count: int = field(default=0, repr=False)
    _half_open_calls: int = field(default=0, repr=False)
    _last_failure_time: Optional[float] = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    async def call(
        self,
        func: Callable[..., Any],
        *args,
        fallback: Optional[T] = None,
        **kwargs,
    ) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if we should try half-open
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"Circuit {self.name}: transitioning to HALF_OPEN")
                else:
                    logger.warning(f"Circuit {self.name}: OPEN - rejecting call")
                    if fallback is not None:
                        return fallback
                    raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN")
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    logger.warning(f"Circuit {self.name}: HALF_OPEN limit reached")
                    if fallback is not None:
                        return fallback
                    raise CircuitBreakerOpen(f"Circuit {self.name} is HALF_OPEN (limit reached)")
                self._half_open_calls += 1
        
        # Execute the call
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            if fallback is not None:
                logger.warning(f"Circuit {self.name}: call failed, using fallback: {e}")
                return fallback
            raise
    
    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name}: CLOSED (recovered)")
            else:
                self._failure_count = 0
    
    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: OPEN (half-open test failed)")
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.error(f"Circuit {self.name}: OPEN ({self._failure_count} failures)")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.config.recovery_timeout
    
    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "half_open_calls": self._half_open_calls,
            "last_failure": self._last_failure_time,
        }


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


# Registry of circuit breakers for different services
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreaker:
    """Get or create a circuit breaker for a service."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            config=config or CircuitBreakerConfig(),
        )
    return _circuit_breakers[name]


def circuit_breaker(
    name: str,
    fallback: Optional[Any] = None,
    config: Optional[CircuitBreakerConfig] = None,
):
    """Decorator to add circuit breaker to a function."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker = get_circuit_breaker(name, config)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, fallback=fallback, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions in async context, we need to handle carefully
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, use the async path
                    return asyncio.create_task(breaker.call(func, *args, fallback=fallback, **kwargs))
                else:
                    return loop.run_until_complete(breaker.call(func, *args, fallback=fallback, **kwargs))
            except RuntimeError:
                # No event loop, create one
                return asyncio.run(breaker.call(func, *args, fallback=fallback, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def get_all_circuit_status() -> dict:
    """Get status of all circuit breakers."""
    return {name: cb.get_status() for name, cb in _circuit_breakers.items()}


# Pre-configured circuit breakers for common services
WORDPRESS_CB_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=120.0,  # 2 minutes
    half_open_max_calls=2,
    success_threshold=1,
)

DATAFORSEO_CB_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=300.0,  # 5 minutes
    half_open_max_calls=3,
    success_threshold=2,
)

ANTHROPIC_CB_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=60.0,  # 1 minute
    half_open_max_calls=2,
    success_threshold=1,
)

WORDPRESS_CB = get_circuit_breaker("wordpress", WORDPRESS_CB_CONFIG)
DATAFORSEO_CB = get_circuit_breaker("dataforseo", DATAFORSEO_CB_CONFIG)
ANTHROPIC_CB = get_circuit_breaker("anthropic", ANTHROPIC_CB_CONFIG)
