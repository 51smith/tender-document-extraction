import time
import asyncio
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
from app.core.exceptions import GeminiRateLimitError


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""

    capacity: int
    tokens: float
    last_update: float
    fill_rate: float  # tokens per second

    def __post_init__(self):
        self.tokens = min(self.tokens, self.capacity)

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket."""
        now = time.time()

        # Add tokens based on elapsed time
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_tokens(self, tokens: int = 1) -> float:
        """Calculate time until we have enough tokens."""
        if self.tokens >= tokens:
            return 0.0

        needed_tokens = tokens - self.tokens
        return needed_tokens / self.fill_rate


class RateLimiter:
    """Rate limiter for Gemini API calls using token bucket algorithm."""

    def __init__(
        self,
        requests_per_minute: int = 300,
        tokens_per_minute: int = 50000,
        burst_requests: Optional[int] = None,
        burst_tokens: Optional[int] = None,
    ):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute

        # Allow some bursting - default to 2x the per-minute rate
        self.burst_requests = burst_requests or min(requests_per_minute * 2, 1000)
        self.burst_tokens = burst_tokens or min(tokens_per_minute * 2, 100000)

        # Convert to per-second rates
        self.request_rate = requests_per_minute / 60.0
        self.token_rate = tokens_per_minute / 60.0

        # Token buckets
        self.request_bucket = RateLimitBucket(
            capacity=self.burst_requests,
            tokens=self.burst_requests,
            last_update=time.time(),
            fill_rate=self.request_rate,
        )

        self.token_bucket = RateLimitBucket(
            capacity=self.burst_tokens,
            tokens=self.burst_tokens,
            last_update=time.time(),
            fill_rate=self.token_rate,
        )

        # Thread safety
        self._lock = threading.Lock()

        # Statistics
        self.stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "rate_limited_requests": 0,
            "last_reset": time.time(),
        }

    def can_make_request(self, estimated_tokens: int = 1000) -> Tuple[bool, Optional[float]]:
        """Check if we can make a request with estimated token usage."""
        with self._lock:
            # Check both request and token limits
            can_request = self.request_bucket.consume(1)
            can_consume_tokens = self.token_bucket.consume(estimated_tokens)

            if can_request and can_consume_tokens:
                return True, None

            # Calculate wait time needed
            request_wait = 0.0 if can_request else self.request_bucket.time_until_tokens(1)
            token_wait = (
                0.0 if can_consume_tokens else self.token_bucket.time_until_tokens(estimated_tokens)
            )

            wait_time = max(request_wait, token_wait)

            # If we consumed one but not the other, we need to refund
            if can_request and not can_consume_tokens:
                self.request_bucket.tokens += 1
            elif can_consume_tokens and not can_request:
                self.token_bucket.tokens += estimated_tokens

            return False, wait_time

    async def wait_for_capacity(
        self, estimated_tokens: int = 1000, max_wait: float = 300.0
    ) -> None:
        """Wait until we have capacity for a request."""
        start_time = time.time()

        while time.time() - start_time < max_wait:
            can_proceed, wait_time = self.can_make_request(estimated_tokens)

            if can_proceed:
                self.stats["total_requests"] += 1
                return

            if wait_time is None:
                wait_time = 1.0

            # Don't wait longer than the max_wait
            wait_time = min(wait_time, max_wait - (time.time() - start_time))

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            self.stats["rate_limited_requests"] += 1

        raise GeminiRateLimitError(retry_after=int(wait_time) if wait_time else 60)

    def record_token_usage(self, actual_tokens: int) -> None:
        """Record actual token usage for statistics."""
        with self._lock:
            self.stats["total_tokens"] += actual_tokens

    def get_current_limits(self) -> Dict[str, float]:
        """Get current rate limit status."""
        with self._lock:
            now = time.time()

            # Update buckets to get current token count
            self.request_bucket.consume(0)
            self.token_bucket.consume(0)

            return {
                "available_requests": self.request_bucket.tokens,
                "max_requests": self.request_bucket.capacity,
                "available_tokens": self.token_bucket.tokens,
                "max_tokens": self.token_bucket.capacity,
                "requests_per_minute": self.requests_per_minute,
                "tokens_per_minute": self.tokens_per_minute,
                "time_until_request": self.request_bucket.time_until_tokens(1),
                "time_until_tokens": self.token_bucket.time_until_tokens(1000),
            }

    def get_stats(self) -> Dict[str, any]:
        """Get usage statistics."""
        with self._lock:
            now = time.time()
            elapsed = now - self.stats["last_reset"]

            return {
                **self.stats,
                "elapsed_seconds": elapsed,
                "requests_per_second": self.stats["total_requests"] / max(elapsed, 1),
                "tokens_per_second": self.stats["total_tokens"] / max(elapsed, 1),
                "rate_limit_percentage": (
                    self.stats["rate_limited_requests"] / max(self.stats["total_requests"], 1) * 100
                ),
            }

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        with self._lock:
            self.stats = {
                "total_requests": 0,
                "total_tokens": 0,
                "rate_limited_requests": 0,
                "last_reset": time.time(),
            }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter

    if _rate_limiter is None:
        from app.config import settings

        _rate_limiter = RateLimiter(
            requests_per_minute=settings.gemini.rate_limit_rpm,
            tokens_per_minute=settings.gemini.rate_limit_tpm,
        )

    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (useful for testing)."""
    global _rate_limiter
    _rate_limiter = None
