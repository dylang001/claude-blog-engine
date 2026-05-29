"""Tests for the circuit breaker pattern implementation."""

import asyncio
import pytest

from content_machine.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    circuit_breaker,
    get_circuit_breaker,
)


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig dataclass."""
    
    def test_default_config(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.half_open_max_calls == 3
        assert config.success_threshold == 2
    
    def test_custom_config(self):
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
        )
        assert config.failure_threshold == 3
        assert config.recovery_timeout == 30.0


class TestCircuitBreaker:
    """Test CircuitBreaker class."""
    
    @pytest.fixture
    def config(self):
        return CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # Fast for testing
            half_open_max_calls=2,
            success_threshold=1,
        )
    
    @pytest.fixture
    def breaker(self, config):
        return CircuitBreaker(name="test", config=config)
    
    @pytest.mark.asyncio
    async def test_successful_call(self, breaker):
        """Test normal successful call."""
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state.value == "closed"
    
    @pytest.mark.asyncio
    async def test_failure_counting(self, breaker):
        """Test that failures are counted."""
        async def fail_func():
            raise ValueError("test error")
        
        # First failure
        with pytest.raises(ValueError):
            await breaker.call(fail_func)
        assert breaker._failure_count == 1
        
        # Second failure (threshold reached)
        with pytest.raises(ValueError):
            await breaker.call(fail_func)
        assert breaker.state.value == "open"
    
    @pytest.mark.asyncio
    async def test_open_circuit_blocks_calls(self, breaker):
        """Test that open circuit blocks calls."""
        # Trigger failure to open circuit
        async def fail_func():
            raise ValueError("error")
        
        # Use try/except instead of pytest.raises for async
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        try:
            await breaker.call(fail_func)  # Opens circuit
        except ValueError:
            pass
        
        # Now circuit is open
        assert breaker.state.value == "open"
        
        # Test blocking
        try:
            await breaker.call(lambda: "should not execute")
            assert False, "Should have raised CircuitBreakerOpen"
        except CircuitBreakerOpen:
            pass  # Expected
    
    @pytest.mark.asyncio
    async def test_fallback_on_open(self, breaker):
        """Test fallback value when circuit is open."""
        async def fail_func():
            raise ValueError("error")
        
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        
        # Call with fallback
        async def expensive():
            return "expensive"
        
        result = await breaker.call(expensive, fallback="default")
        assert result == "default"
    
    @pytest.mark.asyncio
    async def test_half_open_recovery(self, breaker, config):
        """Test recovery through half-open state."""
        async def fail_func():
            raise ValueError("error")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        assert breaker.state.value == "open"
        
        # Wait for timeout
        await asyncio.sleep(config.recovery_timeout + 0.05)
        
        # Next call should transition to half-open and succeed
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state.value == "closed"  # Success threshold is 1
    
    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self, breaker, config):
        """Test that failure in half-open reopens circuit."""
        async def fail_func():
            raise ValueError("error")
        
        # Open circuit
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        
        # Wait for timeout
        await asyncio.sleep(config.recovery_timeout + 0.05)
        
        # Failure in half-open should reopen
        try:
            await breaker.call(fail_func)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected
        
        assert breaker.state.value == "open"
    
    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, breaker):
        """Test that success resets failure counter."""
        async def fail_func():
            raise ValueError("error")
        
        async def success_func():
            return "success"
        
        # One failure
        try:
            await breaker.call(fail_func)
        except ValueError:
            pass
        assert breaker._failure_count == 1
        
        # Success should reset
        await breaker.call(success_func)
        assert breaker._failure_count == 0
    
    def test_get_status(self, breaker):
        """Test getting circuit breaker status."""
        status = breaker.get_status()
        
        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""
    
    def test_get_circuit_breaker_creates_new(self):
        """Test getting a new circuit breaker."""
        cb = get_circuit_breaker("new_service")
        assert cb.name == "new_service"
    
    def test_get_circuit_breaker_returns_existing(self):
        """Test that same circuit breaker is returned."""
        cb1 = get_circuit_breaker("shared_service")
        cb2 = get_circuit_breaker("shared_service")
        assert cb1 is cb2
    
    def test_get_circuit_breaker_with_config(self):
        """Test creating circuit breaker with custom config."""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = get_circuit_breaker("custom_config_service", config)
        assert cb.config.failure_threshold == 10


class TestCircuitBreakerDecorator:
    """Test the circuit breaker decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator on successful function."""
        @circuit_breaker("decorated_test")
        async def test_func():
            return "decorated_success"
        
        result = await test_func()
        assert result == "decorated_success"
    
    @pytest.mark.asyncio
    async def test_decorator_failure(self):
        """Test decorator on failing function."""
        call_count = 0
        
        @circuit_breaker("failing_test", config=CircuitBreakerConfig(failure_threshold=1))
        async def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("decorated error")
        
        # First call - should fail normally
        try:
            await fail_func()
        except ValueError:
            pass
        
        # Second call - circuit should be open
        try:
            await fail_func()
            assert False, "Should have raised CircuitBreakerOpen"
        except CircuitBreakerOpen:
            pass
        
        assert call_count == 1  # Second call was blocked
