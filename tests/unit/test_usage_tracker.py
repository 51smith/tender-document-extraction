"""Comprehensive tests for usage tracking service."""

import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.core.exceptions import ServiceUnavailableError
from app.models.extraction import UsageMetrics
from app.services.usage_tracker import (
    CostCalculation,
    TokenCostCalculator,
    TokenUsageEvent,
    UsageTracker,
    cleanup_usage_tracker,
    get_usage_tracker,
    initialize_usage_tracker,
)


class TestTokenUsageEvent:
    """Tests for TokenUsageEvent dataclass."""

    def test_token_usage_event_creation(self):
        """Test creating a token usage event."""
        event = TokenUsageEvent(
            timestamp=time.time(),
            job_id="job-123",
            model="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=Decimal("0.0075"),
            request_type="single",
            success=True,
        )

        assert event.job_id == "job-123"
        assert event.model == "gemini-2.5-pro"
        assert event.input_tokens == 100
        assert event.output_tokens == 50
        assert event.total_tokens == 150
        assert event.cost_usd == Decimal("0.0075")
        assert event.request_type == "single"
        assert event.success is True

    def test_token_usage_event_batch_type(self):
        """Test token usage event for batch processing."""
        event = TokenUsageEvent(
            timestamp=time.time(),
            job_id="batch-456",
            model="gemini-1.5-flash",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=Decimal("0.225"),
            request_type="batch",
            success=False,
        )

        assert event.request_type == "batch"
        assert event.success is False


class TestCostCalculation:
    """Tests for CostCalculation dataclass."""

    def test_cost_calculation_creation(self):
        """Test creating a cost calculation."""
        cost = CostCalculation(
            input_cost=Decimal("0.001"),
            output_cost=Decimal("0.005"),
            total_cost=Decimal("0.006"),
            currency="USD",
        )

        assert cost.input_cost == Decimal("0.001")
        assert cost.output_cost == Decimal("0.005")
        assert cost.total_cost == Decimal("0.006")
        assert cost.currency == "USD"

    def test_cost_calculation_default_currency(self):
        """Test cost calculation with default currency."""
        cost = CostCalculation(
            input_cost=Decimal("0.001"), output_cost=Decimal("0.005"), total_cost=Decimal("0.006")
        )

        assert cost.currency == "USD"


class TestTokenCostCalculator:
    """Tests for token cost calculator."""

    @pytest.fixture
    def calculator(self):
        """Create cost calculator for testing."""
        return TokenCostCalculator()

    def test_gemini_2_5_pro_cost_calculation(self, calculator):
        """Test cost calculation for Gemini 2.5 Pro."""
        cost = calculator.calculate_cost("gemini-2.5-pro", 1000, 500)

        # Expected: (1000/1M * $1.25) + (500/1M * $5.00) = $0.00125 + $0.0025 = $0.00375
        expected_input = Decimal("0.00125")
        expected_output = Decimal("0.0025")
        expected_total = Decimal("0.00375")

        assert cost.input_cost == expected_input
        assert cost.output_cost == expected_output
        assert cost.total_cost == expected_total

    def test_gemini_1_5_flash_cost_calculation(self, calculator):
        """Test cost calculation for Gemini 1.5 Flash."""
        cost = calculator.calculate_cost("gemini-1.5-flash", 1000000, 500000)

        # Expected: (1M/1M * $0.075) + (500K/1M * $0.30) = $0.075 + $0.15 = $0.225
        expected_input = Decimal("0.075")
        expected_output = Decimal("0.150")
        expected_total = Decimal("0.225")

        assert cost.input_cost == expected_input
        assert cost.output_cost == expected_output
        assert cost.total_cost == expected_total

    def test_unknown_model_uses_default_pricing(self, calculator):
        """Test that unknown models use default (Gemini 2.5 Pro) pricing."""
        cost = calculator.calculate_cost("unknown-model", 1000, 500)

        # Should use Gemini 2.5 Pro pricing
        expected_input = Decimal("0.00125")
        expected_output = Decimal("0.0025")
        expected_total = Decimal("0.00375")

        assert cost.input_cost == expected_input
        assert cost.output_cost == expected_output
        assert cost.total_cost == expected_total

    def test_zero_token_cost_calculation(self, calculator):
        """Test cost calculation with zero tokens."""
        cost = calculator.calculate_cost("gemini-2.5-pro", 0, 0)

        assert cost.input_cost == Decimal("0")
        assert cost.output_cost == Decimal("0")
        assert cost.total_cost == Decimal("0")

    def test_large_token_cost_calculation(self, calculator):
        """Test cost calculation with large token counts."""
        cost = calculator.calculate_cost("gemini-2.5-pro", 10000000, 5000000)

        # 10M input tokens: 10 * $1.25 = $12.50
        # 5M output tokens: 5 * $5.00 = $25.00
        # Total: $37.50
        expected_total = Decimal("37.50")

        assert cost.total_cost == expected_total


class TestUsageTracker:
    """Tests for usage tracker."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return AsyncMock(spec=Redis)

    @pytest.fixture
    def usage_tracker(self):
        """Create usage tracker for testing."""
        with patch("app.services.usage_tracker.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.enable_usage_tracking = True
            mock_settings.cost_alert_threshold = 50.0
            return UsageTracker()

    @pytest.fixture
    def disabled_usage_tracker(self):
        """Create disabled usage tracker for testing."""
        with patch("app.services.usage_tracker.settings") as mock_settings:
            mock_settings.enable_usage_tracking = False
            return UsageTracker()

    def test_usage_tracker_initialization(self, usage_tracker):
        """Test usage tracker initialization."""
        assert usage_tracker.enabled is True
        assert isinstance(usage_tracker.cost_calculator, TokenCostCalculator)
        assert usage_tracker._redis_client is None

    def test_disabled_usage_tracker_initialization(self, disabled_usage_tracker):
        """Test disabled usage tracker initialization."""
        assert disabled_usage_tracker.enabled is False

    @pytest.mark.asyncio
    async def test_initialize_success(self, usage_tracker, mock_redis):
        """Test successful initialization."""
        with patch("app.services.usage_tracker.redis.from_url", return_value=mock_redis):
            await usage_tracker.initialize()

            mock_redis.ping.assert_called_once()
            assert usage_tracker._redis_client == mock_redis

    @pytest.mark.asyncio
    async def test_initialize_disabled(self, disabled_usage_tracker):
        """Test initialization when disabled."""
        await disabled_usage_tracker.initialize()
        assert disabled_usage_tracker._redis_client is None

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, usage_tracker):
        """Test initialization with connection failure."""
        with patch("app.services.usage_tracker.redis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping.side_effect = Exception("Connection failed")
            mock_from_url.return_value = mock_redis

            with pytest.raises(ServiceUnavailableError) as exc_info:
                await usage_tracker.initialize()

            assert "Usage tracking unavailable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cleanup(self, usage_tracker, mock_redis):
        """Test cleanup."""
        usage_tracker._redis_client = mock_redis

        await usage_tracker.cleanup()

        mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_no_client(self, usage_tracker):
        """Test cleanup with no Redis client."""
        await usage_tracker.cleanup()
        # Should not raise exception

    @pytest.mark.asyncio
    async def test_record_usage_success(self, usage_tracker, mock_redis):
        """Test successful usage recording."""
        usage_tracker._redis_client = mock_redis
        job_id = str(uuid4())

        with patch.object(usage_tracker, "_store_usage_event") as mock_store, patch.object(
            usage_tracker, "_update_metrics"
        ) as mock_update, patch.object(usage_tracker, "_check_cost_alerts") as mock_alerts:
            cost = await usage_tracker.record_usage(
                job_id=job_id,
                model="gemini-2.5-pro",
                input_tokens=1000,
                output_tokens=500,
                request_type="single",
                success=True,
            )

            # Verify cost calculation
            assert cost.total_cost == Decimal("0.00375")

            # Verify methods were called
            mock_store.assert_called_once()
            mock_update.assert_called_once()
            mock_alerts.assert_called_once()

            # Verify event data
            event = mock_store.call_args[0][0]
            assert event.job_id == job_id
            assert event.model == "gemini-2.5-pro"
            assert event.total_tokens == 1500
            assert event.success is True

    @pytest.mark.asyncio
    async def test_record_usage_disabled(self, disabled_usage_tracker):
        """Test usage recording when disabled."""
        cost = await disabled_usage_tracker.record_usage(
            job_id="test", model="gemini-2.5-pro", input_tokens=1000, output_tokens=500
        )

        # Should return zero cost
        assert cost.total_cost == Decimal("0")

    @pytest.mark.asyncio
    async def test_record_usage_no_client(self, usage_tracker):
        """Test usage recording with no Redis client."""
        cost = await usage_tracker.record_usage(
            job_id="test", model="gemini-2.5-pro", input_tokens=1000, output_tokens=500
        )

        # Should return zero cost
        assert cost.total_cost == Decimal("0")

    @pytest.mark.asyncio
    async def test_store_usage_event(self, usage_tracker, mock_redis):
        """Test storing usage event."""
        usage_tracker._redis_client = mock_redis

        event = TokenUsageEvent(
            timestamp=time.time(),
            job_id="job-123",
            model="gemini-2.5-pro",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=Decimal("0.00375"),
            request_type="single",
            success=True,
        )

        await usage_tracker._store_usage_event(event)

        # Verify Redis calls
        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called_once()

        # Verify zadd call
        zadd_call = mock_redis.zadd.call_args
        event_key = zadd_call[0][0]
        assert "usage:events:" in event_key

        # Verify expire call (90 days)
        expire_call = mock_redis.expire.call_args
        assert expire_call[0][1] == 86400 * 90

    @pytest.mark.asyncio
    async def test_update_metrics(self, usage_tracker, mock_redis):
        """Test updating aggregated metrics."""
        usage_tracker._redis_client = mock_redis
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline

        event = TokenUsageEvent(
            timestamp=time.time(),
            job_id="job-123",
            model="gemini-2.5-pro",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=Decimal("0.00375"),
            request_type="single",
            success=True,
        )

        await usage_tracker._update_metrics(event)

        # Verify pipeline operations
        mock_pipeline.hincrby.assert_called()
        mock_pipeline.hincrbyfloat.assert_called()
        mock_pipeline.expire.assert_called()
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_cost_alerts_no_alert(self, usage_tracker, mock_redis):
        """Test cost alert check when threshold is not exceeded."""
        usage_tracker._redis_client = mock_redis
        mock_redis.hget.return_value = "25.00"  # Below threshold of 50

        await usage_tracker._check_cost_alerts()

        # Should not set alert
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_cost_alerts_triggered(self, usage_tracker, mock_redis):
        """Test cost alert check when threshold is exceeded."""
        usage_tracker._redis_client = mock_redis
        mock_redis.hget.return_value = "75.00"  # Above threshold of 50

        await usage_tracker._check_cost_alerts()

        # Should set alert
        mock_redis.set.assert_called_once()

        # Verify alert data
        set_call = mock_redis.set.call_args
        alert_key = set_call[0][0]
        alert_data = json.loads(set_call[0][1])

        assert "alert:cost_exceeded:" in alert_key
        assert alert_data["actual_cost"] == 75.00
        assert alert_data["threshold"] == 50.0

    @pytest.mark.asyncio
    async def test_check_cost_alerts_exception(self, usage_tracker, mock_redis):
        """Test cost alert check with Redis exception."""
        usage_tracker._redis_client = mock_redis
        mock_redis.hget.side_effect = Exception("Redis error")

        # Should not raise exception
        await usage_tracker._check_cost_alerts()

    @pytest.mark.asyncio
    async def test_get_usage_metrics_success(self, usage_tracker, mock_redis):
        """Test getting usage metrics."""
        usage_tracker._redis_client = mock_redis

        # Mock Redis responses
        mock_redis.hgetall.side_effect = [
            {  # Overall metrics
                "total_requests": "100",
                "successful_requests": "95",
                "failed_requests": "5",
                "total_tokens": "150000",
                "total_cost_usd": "75.50",
            },
            {"requests": "10", "tokens": "1500"},  # Current hour
            {"requests": "5", "tokens": "750"},  # Previous hour
            {"requests": "25", "tokens": "3750"},  # Today
        ]

        metrics = await usage_tracker.get_usage_metrics()

        assert isinstance(metrics, UsageMetrics)
        assert metrics.total_requests == 100
        assert metrics.successful_extractions == 95
        assert metrics.failed_extractions == 5
        assert metrics.total_tokens_used == 150000
        assert metrics.total_cost == Decimal("75.50")
        assert metrics.requests_last_hour == 10
        assert metrics.requests_last_day == 25

    @pytest.mark.asyncio
    async def test_get_usage_metrics_disabled(self, disabled_usage_tracker):
        """Test getting usage metrics when disabled."""
        metrics = await disabled_usage_tracker.get_usage_metrics()

        assert isinstance(metrics, UsageMetrics)
        assert metrics.total_requests == 0

    @pytest.mark.asyncio
    async def test_get_usage_metrics_exception(self, usage_tracker, mock_redis):
        """Test getting usage metrics with Redis exception."""
        usage_tracker._redis_client = mock_redis
        mock_redis.hgetall.side_effect = Exception("Redis error")

        metrics = await usage_tracker.get_usage_metrics()

        assert isinstance(metrics, UsageMetrics)
        assert metrics.total_requests == 0

    @pytest.mark.asyncio
    async def test_get_usage_by_timeframe_success(self, usage_tracker, mock_redis):
        """Test getting usage by timeframe."""
        usage_tracker._redis_client = mock_redis

        # Mock Redis responses for 3 days
        mock_redis.hgetall.side_effect = [
            {"requests": "10", "tokens": "1500", "cost_usd": "7.50"},
            {"requests": "15", "tokens": "2250", "cost_usd": "11.25"},
            {"requests": "8", "tokens": "1200", "cost_usd": "6.00"},
        ]

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        usage_data = await usage_tracker.get_usage_by_timeframe(start_date, end_date)

        assert len(usage_data) == 3
        assert usage_data[0]["date"] == "20240101"
        assert usage_data[0]["requests"] == 10
        assert usage_data[1]["requests"] == 15
        assert usage_data[2]["requests"] == 8

    @pytest.mark.asyncio
    async def test_get_usage_by_timeframe_disabled(self, disabled_usage_tracker):
        """Test getting usage by timeframe when disabled."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)

        usage_data = await disabled_usage_tracker.get_usage_by_timeframe(start_date, end_date)

        assert usage_data == []

    @pytest.mark.asyncio
    async def test_get_model_usage_breakdown_success(self, usage_tracker, mock_redis):
        """Test getting model usage breakdown."""
        usage_tracker._redis_client = mock_redis

        # Mock keys and responses
        mock_redis.keys.return_value = [
            "usage:model:gemini-2.5-pro",
            "usage:model:gemini-1.5-flash",
        ]

        mock_redis.hgetall.side_effect = [
            {"requests": "75", "tokens": "112500", "cost_usd": "56.25"},
            {"requests": "25", "tokens": "37500", "cost_usd": "2.81"},
        ]

        breakdown = await usage_tracker.get_model_usage_breakdown()

        assert len(breakdown) == 2
        assert "gemini-2.5-pro" in breakdown
        assert "gemini-1.5-flash" in breakdown
        assert breakdown["gemini-2.5-pro"]["requests"] == 75
        assert breakdown["gemini-1.5-flash"]["requests"] == 25

    @pytest.mark.asyncio
    async def test_get_model_usage_breakdown_disabled(self, disabled_usage_tracker):
        """Test getting model usage breakdown when disabled."""
        breakdown = await disabled_usage_tracker.get_model_usage_breakdown()
        assert breakdown == {}

    @pytest.mark.asyncio
    async def test_get_model_usage_breakdown_exception(self, usage_tracker, mock_redis):
        """Test getting model usage breakdown with Redis exception."""
        usage_tracker._redis_client = mock_redis
        mock_redis.keys.side_effect = Exception("Redis error")

        breakdown = await usage_tracker.get_model_usage_breakdown()
        assert breakdown == {}

    @pytest.mark.asyncio
    async def test_reset_metrics_success(self, usage_tracker, mock_redis):
        """Test successful metrics reset."""
        usage_tracker._redis_client = mock_redis

        # Mock keys to delete
        mock_redis.keys.side_effect = [
            ["usage:metrics", "usage:daily:20240101"],  # usage:*
            ["alert:cost_exceeded:20240101"],  # alert:*
        ]

        result = await usage_tracker.reset_metrics()

        assert result is True
        mock_redis.delete.assert_called_once()

        # Verify all keys were deleted
        deleted_keys = mock_redis.delete.call_args[0]
        assert "usage:metrics" in deleted_keys
        assert "usage:daily:20240101" in deleted_keys
        assert "alert:cost_exceeded:20240101" in deleted_keys

    @pytest.mark.asyncio
    async def test_reset_metrics_disabled(self, disabled_usage_tracker):
        """Test metrics reset when disabled."""
        result = await disabled_usage_tracker.reset_metrics()
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_metrics_no_keys(self, usage_tracker, mock_redis):
        """Test metrics reset with no keys to delete."""
        usage_tracker._redis_client = mock_redis
        mock_redis.keys.return_value = []

        result = await usage_tracker.reset_metrics()

        assert result is True
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_metrics_exception(self, usage_tracker, mock_redis):
        """Test metrics reset with Redis exception."""
        usage_tracker._redis_client = mock_redis
        mock_redis.keys.side_effect = Exception("Redis error")

        result = await usage_tracker.reset_metrics()
        assert result is False


class TestGlobalUsageTracker:
    """Tests for global usage tracker functions."""

    def test_get_usage_tracker_singleton(self):
        """Test that get_usage_tracker returns singleton instance."""
        with patch("app.services.usage_tracker._usage_tracker", None):
            tracker1 = get_usage_tracker()
            tracker2 = get_usage_tracker()

            assert tracker1 is tracker2
            assert isinstance(tracker1, UsageTracker)

    def test_get_usage_tracker_existing_instance(self):
        """Test that get_usage_tracker returns existing instance."""
        existing_tracker = UsageTracker()

        with patch("app.services.usage_tracker._usage_tracker", existing_tracker):
            tracker = get_usage_tracker()
            assert tracker is existing_tracker

    @pytest.mark.asyncio
    async def test_initialize_usage_tracker(self):
        """Test initialize_usage_tracker function."""
        mock_tracker = AsyncMock()

        with patch("app.services.usage_tracker.get_usage_tracker", return_value=mock_tracker):
            await initialize_usage_tracker()
            mock_tracker.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_usage_tracker_with_instance(self):
        """Test cleanup_usage_tracker with existing instance."""
        mock_tracker = AsyncMock()

        with patch("app.services.usage_tracker._usage_tracker", mock_tracker):
            await cleanup_usage_tracker()
            mock_tracker.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_usage_tracker_no_instance(self):
        """Test cleanup_usage_tracker with no existing instance."""
        with patch("app.services.usage_tracker._usage_tracker", None):
            # Should not raise exception
            await cleanup_usage_tracker()


class TestUsageTrackerIntegration:
    """Integration tests for usage tracker functionality."""

    @pytest.mark.asyncio
    async def test_full_usage_recording_flow(self, mock_redis):
        """Test complete flow of recording and retrieving usage."""
        with patch("app.services.usage_tracker.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.enable_usage_tracking = True
            mock_settings.cost_alert_threshold = 100.0

            tracker = UsageTracker()
            tracker._redis_client = mock_redis

            # Mock pipeline for metrics update
            mock_pipeline = AsyncMock()
            mock_redis.pipeline.return_value = mock_pipeline

            # Record usage
            job_id = str(uuid4())
            cost = await tracker.record_usage(
                job_id=job_id,
                model="gemini-2.5-pro",
                input_tokens=2000,
                output_tokens=1000,
                request_type="batch",
                success=True,
            )

            # Verify cost calculation
            expected_cost = Decimal("0.0075")  # (2000/1M * 1.25) + (1000/1M * 5.0)
            assert cost.total_cost == expected_cost

            # Verify Redis operations were called
            mock_redis.zadd.assert_called_once()
            mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cost_alert_threshold_monitoring(self, mock_redis):
        """Test cost alert threshold monitoring."""
        with patch("app.services.usage_tracker.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.enable_usage_tracking = True
            mock_settings.cost_alert_threshold = 10.0  # Low threshold for testing

            tracker = UsageTracker()
            tracker._redis_client = mock_redis
            mock_pipeline = AsyncMock()
            mock_redis.pipeline.return_value = mock_pipeline

            # Mock high daily cost
            mock_redis.hget.return_value = "15.00"

            # Record usage (triggers alert check)
            await tracker.record_usage(
                job_id="test-job",
                model="gemini-2.5-pro",
                input_tokens=1000,
                output_tokens=500,
                success=True,
            )

            # Verify alert was set
            mock_redis.set.assert_called_once()
            alert_call = mock_redis.set.call_args
            assert "alert:cost_exceeded:" in alert_call[0][0]

    def test_cost_calculation_accuracy(self):
        """Test accuracy of cost calculations for different scenarios."""
        calculator = TokenCostCalculator()

        # Test various token amounts and models
        test_cases = [
            ("gemini-2.5-pro", 1000, 500, Decimal("0.00375")),
            ("gemini-1.5-flash", 10000, 5000, Decimal("0.002250")),
            ("gemini-1.5-pro", 500000, 250000, Decimal("1.875")),
            ("unknown-model", 1000, 500, Decimal("0.00375")),  # Uses default
        ]

        for model, input_tokens, output_tokens, expected_total in test_cases:
            cost = calculator.calculate_cost(model, input_tokens, output_tokens)
            assert cost.total_cost == expected_total, f"Cost mismatch for {model}"

    @pytest.mark.asyncio
    async def test_timeframe_usage_calculation(self, mock_redis):
        """Test usage calculation over different timeframes."""
        with patch("app.services.usage_tracker.settings") as mock_settings:
            mock_settings.enable_usage_tracking = True

            tracker = UsageTracker()
            tracker._redis_client = mock_redis

            # Mock daily data for 5 days
            daily_data = [
                {"requests": "20", "tokens": "3000", "cost_usd": "15.00"},
                {"requests": "25", "tokens": "3750", "cost_usd": "18.75"},
                {"requests": "30", "tokens": "4500", "cost_usd": "22.50"},
                {"requests": "15", "tokens": "2250", "cost_usd": "11.25"},
                {"requests": "22", "tokens": "3300", "cost_usd": "16.50"},
            ]

            mock_redis.hgetall.side_effect = daily_data

            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 5)

            usage_data = await tracker.get_usage_by_timeframe(start_date, end_date)

            # Verify data structure and content
            assert len(usage_data) == 5
            total_requests = sum(item["requests"] for item in usage_data)
            total_cost = sum(item["cost_usd"] for item in usage_data)

            assert total_requests == 112  # Sum of all requests
            assert total_cost == 84.0  # Sum of all costs
