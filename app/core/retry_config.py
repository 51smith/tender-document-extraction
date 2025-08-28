"""
Unified retry configuration and logic for LLM services.
Implements exponential backoff with jitter and circuit breaker patterns.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, Union

from app.core.exceptions import (
    LLMError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    OllamaConnectionError,
    OpenAIConnectionError,
    OpenAIRateLimitError,
)

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.1
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    
    # Circuit breaker settings
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3
    
    # Exception-specific settings
    retryable_exceptions: tuple = (
        LLMRateLimitError,
        OpenAIRateLimitError,
        OllamaConnectionError,
        OpenAIConnectionError,
    )
    
    non_retryable_exceptions: tuple = (
        LLMQuotaExceededError,
    )


class CircuitBreaker:
    """Circuit breaker implementation for service failures."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0
        
    def can_call(self) -> bool:
        """Check if calls are allowed based on circuit state."""
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if current_time - self.last_failure_time >= self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        else:  # HALF_OPEN
            return self.half_open_calls < self.config.half_open_max_calls
    
    def record_success(self):
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        self.failure_count = 0
        
    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            
    def record_call(self):
        """Record a call attempt in half-open state."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for retry attempt."""
    if config.strategy == RetryStrategy.NO_RETRY:
        return 0.0
    elif config.strategy == RetryStrategy.FIXED_DELAY:
        delay = config.base_delay
    elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
        delay = config.base_delay * attempt
    else:  # EXPONENTIAL_BACKOFF
        delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    
    # Apply maximum delay limit
    delay = min(delay, config.max_delay)
    
    # Add jitter to prevent thundering herd
    if config.jitter_factor > 0:
        jitter = delay * config.jitter_factor * random.random()
        delay += jitter
    
    return delay


class RetryManager:
    """Manages retry logic and circuit breakers for LLM services."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.provider_configs: Dict[str, RetryConfig] = {}
        
    def get_config(self, provider: str) -> RetryConfig:
        """Get retry configuration for provider."""
        if provider not in self.provider_configs:
            self.provider_configs[provider] = self._create_provider_config(provider)
        return self.provider_configs[provider]
    
    def get_circuit_breaker(self, provider: str) -> CircuitBreaker:
        """Get circuit breaker for provider."""
        if provider not in self.circuit_breakers:
            config = self.get_config(provider)
            self.circuit_breakers[provider] = CircuitBreaker(config)
        return self.circuit_breakers[provider]
    
    def _create_provider_config(self, provider: str) -> RetryConfig:
        """Create provider-specific retry configuration."""
        base_config = RetryConfig()
        
        if provider == "gemini":
            # Gemini has higher rate limits, can retry more aggressively
            return RetryConfig(
                max_retries=5,
                base_delay=1.0,
                max_delay=30.0,
                failure_threshold=3,
                recovery_timeout=30.0,
            )
        elif provider == "openai":
            # OpenAI has strict rate limits, be more conservative
            return RetryConfig(
                max_retries=3,
                base_delay=2.0,
                max_delay=60.0,
                failure_threshold=5,
                recovery_timeout=60.0,
            )
        elif provider == "ollama":
            # Ollama is local, can retry more frequently for connection issues
            return RetryConfig(
                max_retries=4,
                base_delay=0.5,
                max_delay=10.0,
                failure_threshold=3,
                recovery_timeout=15.0,
                retryable_exceptions=(
                    OllamaConnectionError,
                    LLMError,  # Include generic LLM errors for Ollama
                ),
            )
        else:
            return base_config
    
    async def execute_with_retry(
        self,
        func: Callable,
        provider: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry logic and circuit breaker."""
        config = self.get_config(provider)
        circuit_breaker = self.get_circuit_breaker(provider)
        
        # Check circuit breaker
        if not circuit_breaker.can_call():
            raise LLMError(f"Circuit breaker is open for {provider} service")
        
        last_exception = None
        
        for attempt in range(1, config.max_retries + 2):  # +1 for initial attempt
            try:
                # Record call attempt for circuit breaker
                circuit_breaker.record_call()
                
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Record success
                circuit_breaker.record_success()
                
                if attempt > 1:
                    logger.info(f"Retry successful for {provider} after {attempt - 1} attempts")
                
                return result
                
            except Exception as exc:
                last_exception = exc
                
                # Check if exception is retryable
                if not self._is_retryable_exception(exc, config):
                    circuit_breaker.record_failure()
                    logger.error(f"Non-retryable exception for {provider}: {exc}")
                    raise exc
                
                # Check if we've exhausted retries
                if attempt > config.max_retries:
                    circuit_breaker.record_failure()
                    logger.error(f"Max retries ({config.max_retries}) exceeded for {provider}")
                    break
                
                # Calculate delay and wait
                delay = calculate_delay(attempt, config)
                logger.warning(
                    f"Retry {attempt}/{config.max_retries} for {provider} "
                    f"after {delay:.2f}s delay. Error: {exc}"
                )
                
                # Handle rate limit specific delays
                if hasattr(exc, 'retry_after') and exc.retry_after:
                    delay = max(delay, float(exc.retry_after))
                
                await asyncio.sleep(delay)
        
        # All retries exhausted
        circuit_breaker.record_failure()
        raise last_exception or LLMError(f"Max retries exceeded for {provider}")
    
    def _is_retryable_exception(self, exc: Exception, config: RetryConfig) -> bool:
        """Check if exception is retryable based on configuration."""
        # Check non-retryable exceptions first
        for non_retryable in config.non_retryable_exceptions:
            if isinstance(exc, non_retryable):
                return False
        
        # Check retryable exceptions
        for retryable in config.retryable_exceptions:
            if isinstance(exc, retryable):
                return True
        
        return False
    
    def reset_circuit_breaker(self, provider: str):
        """Reset circuit breaker for provider (useful for testing)."""
        if provider in self.circuit_breakers:
            circuit_breaker = self.circuit_breakers[provider]
            circuit_breaker.state = CircuitState.CLOSED
            circuit_breaker.failure_count = 0
            circuit_breaker.half_open_calls = 0
    
    def get_circuit_status(self, provider: str) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        if provider not in self.circuit_breakers:
            return {"state": "not_initialized"}
        
        circuit = self.circuit_breakers[provider]
        return {
            "state": circuit.state.value,
            "failure_count": circuit.failure_count,
            "last_failure_time": circuit.last_failure_time,
            "half_open_calls": circuit.half_open_calls,
        }


# Global retry manager instance
_retry_manager: Optional[RetryManager] = None


def get_retry_manager() -> RetryManager:
    """Get the global retry manager instance."""
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = RetryManager()
    return _retry_manager