"""
Test suite for Rate Limiter component - targeting 21 missing lines for 85% coverage.
Focus: Edge cases, error conditions, and timeout scenarios.
"""
import time
from unittest.mock import patch

import pytest

from app.core.exceptions import GeminiRateLimitError
from app.core.rate_limiter import RateLimitBucket, RateLimiter, get_rate_limiter, reset_rate_limiter


class TestRateLimitBucket:
    """Test RateLimitBucket edge cases and insufficient token scenarios."""

    def test_consume_insufficient_tokens(self):
        """Test consume method when tokens are insufficient (line 35)."""
        bucket = RateLimitBucket(
            capacity=10,
            tokens=5.0,  # Only 5 tokens available
            last_update=time.time(),
            fill_rate=0.0,  # No refill to avoid time drift
        )

        # Try to consume more tokens than available
        result = bucket.consume(10)  # Request 10, only have 5
        assert result is False  # Should return False (line 35)
        assert bucket.tokens == 5.0  # Tokens should remain unchanged

    def test_time_until_tokens_calculation(self):
        """Test time_until_tokens when tokens are insufficient (lines 42-43)."""
        bucket = RateLimitBucket(
            capacity=100,
            tokens=10.0,  # Have 10 tokens
            last_update=time.time(),
            fill_rate=5.0,  # 5 tokens per second
        )

        # Request more tokens than available
        time_needed = bucket.time_until_tokens(30)  # Need 30, have 10

        # Should calculate: (30 - 10) / 5 = 4.0 seconds
        expected_time = (30 - 10) / 5.0
        assert abs(time_needed - expected_time) < 0.01
        assert time_needed == 4.0

    def test_time_until_tokens_sufficient(self):
        """Test time_until_tokens when tokens are sufficient."""
        bucket = RateLimitBucket(capacity=100, tokens=50.0, last_update=time.time(), fill_rate=10.0)

        # Request fewer tokens than available
        time_needed = bucket.time_until_tokens(25)
        assert time_needed == 0.0  # No wait needed


class TestRateLimiterAdvanced:
    """Test RateLimiter advanced scenarios and error conditions."""

    def test_rate_limiting_refund_logic(self):
        """Test refund logic when one bucket succeeds but other fails (lines 112-115)."""
        limiter = RateLimiter(
            requests_per_minute=60,  # 1 req/sec
            tokens_per_minute=600,  # 10 tokens/sec
        )

        # Exhaust token bucket but keep request bucket full
        limiter.token_bucket.tokens = 5.0  # Very low tokens
        limiter.request_bucket.tokens = 10.0  # Plenty of requests

        # Try to make request requiring many tokens
        can_proceed, wait_time = limiter.can_make_request(estimated_tokens=1000)

        # Should fail and refund the consumed request token
        assert can_proceed is False
        assert wait_time is not None
        assert wait_time > 0
        # Request token should be refunded (line 113)
        assert limiter.request_bucket.tokens >= 10.0

    def test_rate_limiting_reverse_refund(self):
        """Test refund when token bucket succeeds but request fails (lines 114-115)."""
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=60000,  # High token limit
        )

        # Exhaust request bucket but keep token bucket full
        limiter.request_bucket.tokens = 0.1  # Very low requests
        limiter.token_bucket.tokens = 10000.0  # Plenty of tokens

        # Try to make small token request
        can_proceed, wait_time = limiter.can_make_request(estimated_tokens=100)

        # Should fail and refund the consumed tokens
        assert can_proceed is False
        assert wait_time is not None
        # Tokens should be refunded (line 115)
        assert limiter.token_bucket.tokens >= 10000.0

    def test_wait_time_calculation_complex(self):
        """Test complex wait time calculation (lines 104-109)."""
        limiter = RateLimiter(
            requests_per_minute=120,  # 2 req/sec
            tokens_per_minute=1200,  # 20 tokens/sec
        )

        # Set specific token levels
        limiter.request_bucket.tokens = 0.0
        limiter.token_bucket.tokens = 5.0

        can_proceed, wait_time = limiter.can_make_request(estimated_tokens=50)

        assert can_proceed is False
        assert wait_time is not None

        # Wait time should be the maximum of request_wait and token_wait
        request_wait = 1.0 / (120.0 / 60.0)  # 0.5 seconds for 1 request
        token_wait = (50 - 5) / (1200.0 / 60.0)  # 2.25 seconds for 45 tokens
        expected_wait = max(request_wait, token_wait)

        assert abs(wait_time - expected_wait) < 0.1

    @pytest.mark.asyncio()
    @pytest.mark.asyncio()
    async def test_wait_for_capacity_timeout(self):
        """Test wait_for_capacity timeout scenario (lines 132-143)."""
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=600,
        )

        # Exhaust both buckets
        limiter.request_bucket.tokens = 0.0
        limiter.token_bucket.tokens = 0.0

        # Set very slow refill rates
        limiter.request_bucket.fill_rate = 0.1  # Very slow
        limiter.token_bucket.fill_rate = 1.0

        # Should timeout quickly
        start_time = time.time()
        with pytest.raises(GeminiRateLimitError) as exc_info:
            await limiter.wait_for_capacity(estimated_tokens=100, max_wait=0.1)

        elapsed = time.time() - start_time
        assert elapsed < 1.0  # Should timeout quickly
        # Check that retry_after is properly set (could be 0 or 60)
        assert exc_info.value.retry_after is not None

        # Should increment rate_limited_requests counter (line 141)
        assert limiter.stats["rate_limited_requests"] > 0

    @pytest.mark.asyncio()
    @pytest.mark.asyncio()
    async def test_wait_for_capacity_none_wait_time(self):
        """Test wait_for_capacity with None wait_time (lines 132-133)."""
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=600,
        )

        # Mock can_make_request to return None wait_time
        original_can_make_request = limiter.can_make_request

        def mock_can_make_request(*args, **kwargs):
            # First call returns False, None (line 132 case)
            if not hasattr(mock_can_make_request, "called"):
                mock_can_make_request.called = True
                return False, None
            # Second call succeeds
            return original_can_make_request(*args, **kwargs)

        limiter.can_make_request = mock_can_make_request

        # Should handle None wait_time and set to 1.0 (line 133)
        with patch("asyncio.sleep") as mock_sleep:
            await limiter.wait_for_capacity(estimated_tokens=10, max_wait=5.0)
            mock_sleep.assert_called()
            # Should have called sleep with 1.0 when wait_time was None
            assert any(call.args[0] == 1.0 for call in mock_sleep.call_args_list)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio()
    async def test_wait_for_capacity_time_limiting(self):
        """Test wait_for_capacity time limiting logic (line 136)."""
        limiter = RateLimiter(
            requests_per_minute=60,
            tokens_per_minute=600,
        )

        # Set buckets to require waiting
        limiter.request_bucket.tokens = 0.0
        limiter.token_bucket.tokens = 0.0

        # Use a simpler approach without extensive mocking
        start_time = time.time()
        try:
            await limiter.wait_for_capacity(estimated_tokens=100, max_wait=0.1)
        except GeminiRateLimitError:
            pass  # Expected timeout

        elapsed = time.time() - start_time
        # Should respect the max_wait time limit
        assert elapsed <= 0.5  # Allow some tolerance for execution time

    def test_reset_stats_method(self):
        """Test reset_stats method (lines 188-194)."""
        limiter = RateLimiter()

        # Add some statistics
        limiter.stats["total_requests"] = 100
        limiter.stats["total_tokens"] = 5000
        limiter.stats["rate_limited_requests"] = 10

        # Reset stats
        limiter.reset_stats()

        # All stats should be reset
        assert limiter.stats["total_requests"] == 0
        assert limiter.stats["total_tokens"] == 0
        assert limiter.stats["rate_limited_requests"] == 0
        assert "last_reset" in limiter.stats
        assert isinstance(limiter.stats["last_reset"], float)


class TestGlobalRateLimiter:
    """Test global rate limiter functions."""

    def test_reset_rate_limiter_function(self):
        """Test reset_rate_limiter global function (line 219)."""
        # First create a rate limiter
        limiter1 = get_rate_limiter()
        assert limiter1 is not None

        # Reset global limiter
        reset_rate_limiter()

        # Next get_rate_limiter should create a new instance
        limiter2 = get_rate_limiter()
        assert limiter2 is not None
        # Should be different instance (new object created)
        assert limiter2 is not limiter1

    def test_get_rate_limiter_configuration(self):
        """Test get_rate_limiter with custom settings."""
        # Reset to force new creation
        reset_rate_limiter()

        # Patch the config import
        with patch("app.config.settings") as mock_settings:
            mock_settings.gemini_rate_limit_rpm = 200
            mock_settings.gemini_rate_limit_tpm = 40000

            limiter = get_rate_limiter()

            assert limiter.requests_per_minute == 200
            assert limiter.tokens_per_minute == 40000


class TestEdgeCases:
    """Test additional edge cases for complete coverage."""

    def test_bucket_token_refill_over_capacity(self):
        """Test that token refill doesn't exceed capacity."""
        bucket = RateLimitBucket(
            capacity=10,
            tokens=8.0,
            last_update=time.time() - 10,  # 10 seconds ago
            fill_rate=5.0,  # Would add 50 tokens in 10 seconds
        )

        # Consume 0 tokens to trigger refill
        bucket.consume(0)

        # Should be capped at capacity
        assert bucket.tokens == 10.0  # Not 58.0

    def test_zero_fill_rate_bucket(self):
        """Test bucket with zero fill rate."""
        bucket = RateLimitBucket(
            capacity=10, tokens=5.0, last_update=time.time(), fill_rate=0.0  # No refill
        )

        # Should never refill
        time.sleep(0.1)
        initial_tokens = bucket.tokens
        bucket.consume(0)  # Trigger update

        assert bucket.tokens == initial_tokens

    @pytest.mark.asyncio()
    @pytest.mark.asyncio()
    async def test_successful_wait_for_capacity(self):
        """Test successful wait_for_capacity completion."""
        limiter = RateLimiter(
            requests_per_minute=6000,  # High limits
            tokens_per_minute=60000,
        )

        # Should succeed immediately
        await limiter.wait_for_capacity(estimated_tokens=100, max_wait=1.0)

        # Should increment total_requests counter
        assert limiter.stats["total_requests"] == 1
