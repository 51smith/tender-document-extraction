"""Error recovery test scenarios for LLM services and circuit breakers."""

import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    LLMError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    OllamaConnectionError,
    OpenAIConnectionError,
    OpenAIRateLimitError,
)
from app.core.retry_config import (
    CircuitBreaker,
    CircuitState,
    RetryConfig,
    RetryManager,
    RetryStrategy,
    calculate_delay,
    get_retry_manager,
)
from app.services.llm_service import GeminiLLMService, OllamaLLMService, OpenAILLMService


class TestRetryConfiguration:
    """Test retry configuration and delay calculations."""

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
            jitter_factor=0.0,  # No jitter for predictable testing
        )

        # Test exponential growth
        assert calculate_delay(1, config) == 1.0
        assert calculate_delay(2, config) == 2.0
        assert calculate_delay(3, config) == 4.0
        assert calculate_delay(4, config) == 8.0

        # Test max delay capping
        assert calculate_delay(5, config) == 10.0  # Capped at max_delay
        assert calculate_delay(10, config) == 10.0

    def test_linear_backoff_calculation(self):
        """Test linear backoff delay calculation."""
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR_BACKOFF, base_delay=2.0, max_delay=20.0, jitter_factor=0.0
        )

        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0
        assert calculate_delay(3, config) == 6.0
        assert calculate_delay(10, config) == 20.0  # Capped

    def test_fixed_delay_calculation(self):
        """Test fixed delay calculation."""
        config = RetryConfig(strategy=RetryStrategy.FIXED_DELAY, base_delay=3.0, jitter_factor=0.0)

        for attempt in range(1, 10):
            assert calculate_delay(attempt, config) == 3.0

    def test_jitter_application(self):
        """Test jitter is applied to delays."""
        config = RetryConfig(
            base_delay=10.0,
            jitter_factor=0.2,  # 20% jitter
        )

        delays = [calculate_delay(1, config) for _ in range(100)]

        # All delays should be >= base_delay (10.0)
        assert all(d >= 10.0 for d in delays)
        # Some delays should be > base_delay due to jitter
        assert any(d > 10.0 for d in delays)
        # Max jitter adds 20% of base_delay
        assert all(d <= 12.0 for d in delays)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.fixture()
    @pytest.fixture
    def circuit_config(self):
        """Circuit breaker configuration for testing."""
        return RetryConfig(failure_threshold=3, recovery_timeout=5.0, half_open_max_calls=2)

    def test_circuit_breaker_initial_state(self, circuit_config):
        """Test initial circuit breaker state."""
        breaker = CircuitBreaker(circuit_config)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.can_call() is True

    def test_circuit_breaker_failure_progression(self, circuit_config):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(circuit_config)

        # Record failures below threshold
        for _i in range(circuit_config.failure_threshold - 1):
        for i in range(circuit_config.failure_threshold - 1):
            breaker.record_failure()
            assert breaker.state == CircuitState.CLOSED
            assert breaker.can_call() is True

        # Final failure should open circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.can_call() is False

    def test_circuit_breaker_recovery(self, circuit_config):
        """Test circuit breaker recovery after timeout."""
        breaker = CircuitBreaker(circuit_config)

        # Force circuit open
        for _ in range(circuit_config.failure_threshold):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        # Simulate time passing (mock time.time)
        with patch("time.time") as mock_time:
            # Initially at failure time
            mock_time.return_value = breaker.last_failure_time
            assert breaker.can_call() is False

            # After recovery timeout
            mock_time.return_value = breaker.last_failure_time + circuit_config.recovery_timeout + 1
            assert breaker.can_call() is True
            assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_state_behavior(self, circuit_config):
        """Test half-open state behavior."""
        breaker = CircuitBreaker(circuit_config)

        # Force to half-open state
        breaker.state = CircuitState.HALF_OPEN
        breaker.half_open_calls = 0

        # Should allow calls up to limit
        assert breaker.can_call() is True
        breaker.record_call()
        assert breaker.half_open_calls == 1

        assert breaker.can_call() is True
        breaker.record_call()
        assert breaker.half_open_calls == 2

        # Should not allow more calls
        assert breaker.can_call() is False

    def test_half_open_success_closes_circuit(self, circuit_config):
        """Test successful call in half-open state closes circuit."""
        breaker = CircuitBreaker(circuit_config)
        breaker.state = CircuitState.HALF_OPEN

        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_half_open_failure_opens_circuit(self, circuit_config):
        """Test failure in half-open state opens circuit."""
        breaker = CircuitBreaker(circuit_config)
        breaker.state = CircuitState.HALF_OPEN

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN


class TestRetryManager:
    """Test retry manager functionality."""

    @pytest.fixture()
    @pytest.fixture
    def retry_manager(self):
        """Create retry manager for testing."""
        return RetryManager()

    def test_provider_config_creation(self, retry_manager):
        """Test provider-specific configuration creation."""
        gemini_config = retry_manager.get_config("gemini")
        openai_config = retry_manager.get_config("openai")
        ollama_config = retry_manager.get_config("ollama")

        # Verify different providers have different configs
        assert gemini_config.max_retries == 5
        assert openai_config.max_retries == 3
        assert ollama_config.max_retries == 4

        # Verify recovery timeouts are different
        assert gemini_config.recovery_timeout == 30.0
        assert openai_config.recovery_timeout == 60.0
        assert ollama_config.recovery_timeout == 15.0

    def test_circuit_breaker_per_provider(self, retry_manager):
        """Test separate circuit breakers per provider."""
        gemini_breaker = retry_manager.get_circuit_breaker("gemini")
        openai_breaker = retry_manager.get_circuit_breaker("openai")

        assert gemini_breaker is not openai_breaker

        # Affect one provider
        gemini_breaker.record_failure()
        assert gemini_breaker.failure_count == 1
        assert openai_breaker.failure_count == 0

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self, retry_manager):
        """Test successful execution requires no retry."""
        mock_func = AsyncMock(return_value="success")

        result = await retry_manager.execute_with_retry(
            mock_func, "test_provider", "arg1", kwarg1="value1"
        )

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_retry_on_retryable_exception(self, retry_manager):
        """Test retry behavior on retryable exceptions."""
        mock_func = AsyncMock()
        # First call fails, second succeeds
        mock_func.side_effect = [LLMRateLimitError("rate limited"), "success"]

        with patch("asyncio.sleep") as mock_sleep:
            result = await retry_manager.execute_with_retry(mock_func, "test_provider")

        assert result == "success"
        assert mock_func.call_count == 2
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_exception(self, retry_manager):
        """Test no retry on non-retryable exceptions."""
        mock_func = AsyncMock()
        mock_func.side_effect = LLMQuotaExceededError("quota exceeded")

        with pytest.raises(LLMQuotaExceededError):
            await retry_manager.execute_with_retry(mock_func, "test_provider")

        # Should only be called once (no retry)
        mock_func.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, retry_manager):
        """Test behavior when max retries are exhausted."""
        mock_func = AsyncMock()
        mock_func.side_effect = LLMRateLimitError("persistent error")

        with patch("asyncio.sleep"), pytest.raises(LLMRateLimitError):
            await retry_manager.execute_with_retry(mock_func, "test_provider")

        # Should be called max_retries + 1 times (initial + retries)
        config = retry_manager.get_config("test_provider")
        assert mock_func.call_count == config.max_retries + 1

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_calls(self, retry_manager):
        """Test circuit breaker blocks calls when open."""
        # Manually open the circuit breaker
        breaker = retry_manager.get_circuit_breaker("test_provider")
        breaker.state = CircuitState.OPEN
        breaker.last_failure_time = time.time()  # Set recent failure time

        mock_func = AsyncMock()

        with pytest.raises(LLMError) as exc_info:
            await retry_manager.execute_with_retry(mock_func, "test_provider")

        assert "Circuit breaker is open" in str(exc_info.value)
        mock_func.assert_not_called()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_retry_after_handling(self, retry_manager):
        """Test handling of retry_after in rate limit exceptions."""
        mock_func = AsyncMock()
        rate_limit_error = LLMRateLimitError("rate limited")
        rate_limit_error.retry_after = 30  # 30 seconds
        mock_func.side_effect = [rate_limit_error, "success"]

        with patch("asyncio.sleep") as mock_sleep:
            result = await retry_manager.execute_with_retry(mock_func, "test_provider")

        assert result == "success"
        # Should sleep for at least the retry_after time
        sleep_call = mock_sleep.call_args[0][0]
        assert sleep_call >= 30.0


class TestLLMServiceIntegration:
    """Test LLM service integration with retry logic."""

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_service_retry_integration(self):
        """Test Gemini service integrates with retry manager."""
        with patch("app.services.llm_service.genai"):
            service = GeminiLLMService("test-key", "gemini-pro")

            # Mock the internal implementation to fail then succeed
            with patch.object(service, "_generate_content_impl") as mock_impl:
                mock_impl.side_effect = [LLMRateLimitError("rate limited"), {"response": "success"}]

                with patch("asyncio.sleep"):
                    result = await service.generate_content("test prompt")

                assert result == {"response": "success"}
                assert mock_impl.call_count == 2

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_openai_service_retry_integration(self):
        """Test OpenAI service integrates with retry manager."""
        with patch("app.services.llm_service.openai.AsyncOpenAI"):
            service = OpenAILLMService("test-key", "gpt-4")

            with patch.object(service, "_generate_content_impl") as mock_impl:
                mock_impl.side_effect = [
                    OpenAIConnectionError("connection failed"),
                    {"response": "success"},
                ]

                with patch("asyncio.sleep"):
                    result = await service.generate_content("test prompt")

                assert result == {"response": "success"}
                assert mock_impl.call_count == 2

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_ollama_service_retry_integration(self):
        """Test Ollama service integrates with retry manager."""
        service = OllamaLLMService("http://localhost:11434", "llama2")

        with patch.object(service, "_generate_content_impl") as mock_impl:
            mock_impl.side_effect = [
                OllamaConnectionError("http://localhost:11434", "connection refused"),
                {"response": "success"},
            ]

            with patch("asyncio.sleep"):
                result = await service.generate_content("test prompt")

            assert result == {"response": "success"}
            assert mock_impl.call_count == 2

    def test_circuit_status_reporting(self):
        """Test circuit breaker status reporting."""
        with patch("app.services.llm_service.genai"):
            service = GeminiLLMService("test-key", "gemini-pro")

            # Initial status
            status = service.get_circuit_status()
            assert status["state"] == "closed"
            assert status["failure_count"] == 0

            # Cause failures
            breaker = service.retry_manager.get_circuit_breaker("gemini")
            breaker.record_failure()

            status = service.get_circuit_status()
            assert status["failure_count"] == 1

    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        with patch("app.services.llm_service.genai"):
            service = GeminiLLMService("test-key", "gemini-pro")

            # Force circuit open
            breaker = service.retry_manager.get_circuit_breaker("gemini")
            breaker.state = CircuitState.OPEN
            breaker.failure_count = 5

            # Reset
            service.reset_circuit_breaker()

            status = service.get_circuit_status()
            assert status["state"] == "closed"
            assert status["failure_count"] == 0


class TestNetworkFailureRecovery:
    """Test network failure recovery scenarios."""

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_network_failure_recovery(self):
        """Test recovery from network failures."""
        retry_manager = RetryManager()

        mock_func = AsyncMock()
        # Simulate network issues followed by recovery
        mock_func.side_effect = [
            OllamaConnectionError("localhost", "connection refused"),
            OllamaConnectionError("localhost", "timeout"),
            {"response": "recovered"},
        ]

        with patch("asyncio.sleep"):
            result = await retry_manager.execute_with_retry(mock_func, "ollama")

        assert result == {"response": "recovered"}
        assert mock_func.call_count == 3

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_quota_exhaustion_handling(self):
        """Test quota exhaustion handling (no retry)."""
        retry_manager = RetryManager()

        mock_func = AsyncMock()
        mock_func.side_effect = LLMQuotaExceededError("monthly quota exceeded")

        with pytest.raises(LLMQuotaExceededError):
            await retry_manager.execute_with_retry(mock_func, "gemini")

        # Should not retry quota errors
        mock_func.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_provider_failover_scenarios(self):
        """Test provider failover scenarios."""
        retry_manager = RetryManager()

        # Simulate primary provider circuit open
        primary_breaker = retry_manager.get_circuit_breaker("gemini")
        primary_breaker.state = CircuitState.OPEN

        # Fallback should work (different provider)
        fallback_func = AsyncMock(return_value={"response": "fallback success"})

        result = await retry_manager.execute_with_retry(
            fallback_func, "openai"  # Different provider
        )

        assert result == {"response": "fallback success"}

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_partial_batch_processing_failures(self):
        """Test handling of partial batch processing failures."""
        retry_manager = RetryManager()

        # Simulate processing multiple documents where some fail
        results = []

        async def process_document(doc_id):
            """Mock document processing."""
            if doc_id == "doc2":
                raise LLMRateLimitError("rate limited")
            return f"processed {doc_id}"

        # Process batch with retries
        documents = ["doc1", "doc2", "doc3"]
        failed_docs = []

        for doc_id in documents:
            try:
                with patch("asyncio.sleep"):
                    result = await retry_manager.execute_with_retry(
                        process_document, "gemini", doc_id
                    )
                results.append(result)
            except LLMRateLimitError:
                failed_docs.append(doc_id)

        # Should have processed doc1 and doc3, failed on doc2
        assert len(results) == 2
        assert "processed doc1" in results
        assert "processed doc3" in results
        assert "doc2" in failed_docs


class TestErrorRecoveryMetrics:
    """Test error recovery metrics and monitoring."""

    def test_retry_manager_singleton(self):
        """Test retry manager singleton pattern."""
        manager1 = get_retry_manager()
        manager2 = get_retry_manager()

        assert manager1 is manager2

    def test_circuit_status_reporting(self):
        """Test comprehensive circuit status reporting."""
        retry_manager = RetryManager()

        # Test uninitialized status
        status = retry_manager.get_circuit_status("nonexistent")
        assert status == {"state": "not_initialized"}

        # Initialize circuit breaker
        breaker = retry_manager.get_circuit_breaker("test")
        breaker.failure_count = 2
        breaker.half_open_calls = 1

        status = retry_manager.get_circuit_status("test")
        assert status["state"] == "closed"
        assert status["failure_count"] == 2
        assert status["half_open_calls"] == 1
        assert "last_failure_time" in status

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_error_logging_during_retries(self):
        """Test proper error logging during retry attempts."""
        retry_manager = RetryManager()
        mock_func = AsyncMock()

        errors = [
            LLMRateLimitError("rate limited"),
            OpenAIConnectionError("connection failed"),
            "success",
        ]
        mock_func.side_effect = errors

        with patch("asyncio.sleep"), patch("app.core.retry_config.logger") as mock_logger:
            result = await retry_manager.execute_with_retry(mock_func, "test")

            assert result == "success"

            # Should log warnings for retries
            warning_calls = list(mock_logger.warning.call_args_list)
            warning_calls = [call for call in mock_logger.warning.call_args_list]
            assert len(warning_calls) == 2  # Two retry attempts

            # Verify retry messages contain attempt numbers
            assert "Retry 1/3" in str(warning_calls[0])
            assert "Retry 2/3" in str(warning_calls[1])
