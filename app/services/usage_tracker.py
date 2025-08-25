import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from app.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.models.extraction import UsageMetrics

logger = logging.getLogger(__name__)


@dataclass
class TokenUsageEvent:
    """Represents a token usage event."""

    timestamp: float
    job_id: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal
    request_type: str  # "single", "batch"
    success: bool


@dataclass
class CostCalculation:
    """Cost calculation result."""

    input_cost: Decimal
    output_cost: Decimal
    total_cost: Decimal
    currency: str = "USD"


class TokenCostCalculator:
    """Calculates costs for different models and token types."""

    # Gemini 2.5 Pro pricing (as of 2024) - prices per 1M tokens
    MODEL_PRICING = {
        "gemini-2.5-pro": {
            "input_cost_per_1m": Decimal("1.25"),  # $1.25 per 1M input tokens
            "output_cost_per_1m": Decimal("5.00"),  # $5.00 per 1M output tokens
        },
        "gemini-1.5-pro": {
            "input_cost_per_1m": Decimal("1.25"),
            "output_cost_per_1m": Decimal("5.00"),
        },
        "gemini-1.5-flash": {
            "input_cost_per_1m": Decimal("0.075"),  # $0.075 per 1M input tokens
            "output_cost_per_1m": Decimal("0.30"),  # $0.30 per 1M output tokens
        },
    }

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> CostCalculation:
        """Calculate cost for token usage."""

        pricing = self.MODEL_PRICING.get(model, self.MODEL_PRICING["gemini-2.5-pro"])

        # Calculate costs
        input_cost = (Decimal(input_tokens) / Decimal("1000000")) * pricing["input_cost_per_1m"]
        output_cost = (Decimal(output_tokens) / Decimal("1000000")) * pricing["output_cost_per_1m"]
        total_cost = input_cost + output_cost

        return CostCalculation(
            input_cost=input_cost, output_cost=output_cost, total_cost=total_cost
        )


class UsageTracker:
    """Tracks API usage, token consumption, and costs."""

    def __init__(self):
        self.redis_url = settings.redis_url
        self.cost_calculator = TokenCostCalculator()
        self._redis_client: Optional[redis.Redis] = None
        self.enabled = settings.enable_usage_tracking

    async def initialize(self):
        """Initialize Redis connection."""
        if not self.enabled:
            logger.info("Usage tracking is disabled")
            return

        try:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self._redis_client.ping()
            logger.info("Usage tracker initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize usage tracker: {e}")
            raise ServiceUnavailableError(f"Usage tracking unavailable: {str(e)}")

    async def cleanup(self):
        """Clean up Redis connection."""
        if self._redis_client:
            await self._redis_client.close()

    async def record_usage(
        self,
        job_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        request_type: str = "single",
        success: bool = True,
    ) -> CostCalculation:
        """Record token usage and calculate costs."""

        if not self.enabled or not self._redis_client:
            return CostCalculation(
                input_cost=Decimal("0"), output_cost=Decimal("0"), total_cost=Decimal("0")
            )

        total_tokens = input_tokens + output_tokens
        cost = self.cost_calculator.calculate_cost(model, input_tokens, output_tokens)

        # Create usage event
        event = TokenUsageEvent(
            timestamp=time.time(),
            job_id=job_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost.total_cost,
            request_type=request_type,
            success=success,
        )

        # Store the event
        await self._store_usage_event(event)

        # Update aggregated metrics
        await self._update_metrics(event)

        # Check cost alerts
        await self._check_cost_alerts()

        logger.info(
            f"Recorded usage: {total_tokens} tokens, ${cost.total_cost:.4f} for job {job_id}"
        )

        return cost

    async def _store_usage_event(self, event: TokenUsageEvent):
        """Store individual usage event."""

        # Store in sorted set by timestamp for time-based queries
        event_key = f"usage:events:{datetime.fromtimestamp(event.timestamp).strftime('%Y%m%d')}"
        event_data = {
            "job_id": event.job_id,
            "model": event.model,
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "total_tokens": event.total_tokens,
            "cost_usd": float(event.cost_usd),
            "request_type": event.request_type,
            "success": event.success,
        }

        await self._redis_client.zadd(event_key, {json.dumps(event_data): event.timestamp})

        # Set expiration for 90 days
        await self._redis_client.expire(event_key, 86400 * 90)

    async def _update_metrics(self, event: TokenUsageEvent):
        """Update aggregated metrics."""

        pipe = self._redis_client.pipeline()

        # Update overall counters
        pipe.hincrby("usage:metrics", "total_requests", 1)
        pipe.hincrby("usage:metrics", "total_tokens", event.total_tokens)
        pipe.hincrbyfloat("usage:metrics", "total_cost_usd", float(event.cost_usd))

        if event.success:
            pipe.hincrby("usage:metrics", "successful_requests", 1)
        else:
            pipe.hincrby("usage:metrics", "failed_requests", 1)

        # Update hourly counters
        current_hour = datetime.fromtimestamp(event.timestamp).strftime("%Y%m%d%H")
        pipe.hincrby(f"usage:hourly:{current_hour}", "requests", 1)
        pipe.hincrby(f"usage:hourly:{current_hour}", "tokens", event.total_tokens)
        pipe.hincrbyfloat(f"usage:hourly:{current_hour}", "cost_usd", float(event.cost_usd))
        pipe.expire(f"usage:hourly:{current_hour}", 86400 * 7)  # Keep for 7 days

        # Update daily counters
        current_day = datetime.fromtimestamp(event.timestamp).strftime("%Y%m%d")
        pipe.hincrby(f"usage:daily:{current_day}", "requests", 1)
        pipe.hincrby(f"usage:daily:{current_day}", "tokens", event.total_tokens)
        pipe.hincrbyfloat(f"usage:daily:{current_day}", "cost_usd", float(event.cost_usd))
        pipe.expire(f"usage:daily:{current_day}", 86400 * 90)  # Keep for 90 days

        # Update model-specific counters
        pipe.hincrby(f"usage:model:{event.model}", "requests", 1)
        pipe.hincrby(f"usage:model:{event.model}", "tokens", event.total_tokens)
        pipe.hincrbyfloat(f"usage:model:{event.model}", "cost_usd", float(event.cost_usd))

        await pipe.execute()

    async def _check_cost_alerts(self):
        """Check if cost thresholds are exceeded."""

        try:
            # Get today's cost
            today = datetime.now().strftime("%Y%m%d")
            daily_cost = await self._redis_client.hget(f"usage:daily:{today}", "cost_usd")

            if daily_cost:
                daily_cost = float(daily_cost)
                threshold = float(settings.cost_alert_threshold)

                if daily_cost > threshold:
                    logger.warning(
                        f"Daily cost threshold exceeded: ${daily_cost:.2f} > ${threshold:.2f}"
                    )

                    # In a real implementation, you'd send alerts via email/Slack/etc.
                    await self._redis_client.set(
                        f"alert:cost_exceeded:{today}",
                        json.dumps(
                            {
                                "date": today,
                                "actual_cost": daily_cost,
                                "threshold": threshold,
                                "timestamp": time.time(),
                            }
                        ),
                        ex=86400,  # Expire after 24 hours
                    )

        except Exception as e:
            logger.error(f"Error checking cost alerts: {e}")

    async def get_usage_metrics(self) -> UsageMetrics:
        """Get current usage metrics."""

        if not self.enabled or not self._redis_client:
            return UsageMetrics()

        try:
            # Get overall metrics
            metrics_data = await self._redis_client.hgetall("usage:metrics")

            # Get hourly metrics (last hour)
            current_hour = datetime.now().strftime("%Y%m%d%H")
            prev_hour = (datetime.now() - timedelta(hours=1)).strftime("%Y%m%d%H")

            current_hour_data = await self._redis_client.hgetall(f"usage:hourly:{current_hour}")
            prev_hour_data = await self._redis_client.hgetall(f"usage:hourly:{prev_hour}")

            # Get daily metrics (today)
            today = datetime.now().strftime("%Y%m%d")
            daily_data = await self._redis_client.hgetall(f"usage:daily:{today}")

            # Build metrics object
            return UsageMetrics(
                total_requests=int(metrics_data.get("total_requests", 0)),
                successful_extractions=int(metrics_data.get("successful_requests", 0)),
                failed_extractions=int(metrics_data.get("failed_requests", 0)),
                total_tokens_used=int(metrics_data.get("total_tokens", 0)),
                total_cost=Decimal(str(metrics_data.get("total_cost_usd", "0.00"))),
                requests_last_hour=int(current_hour_data.get("requests", 0)),
                requests_last_day=int(daily_data.get("requests", 0)),
                tokens_last_hour=int(current_hour_data.get("tokens", 0)),
                tokens_last_day=int(daily_data.get("tokens", 0)),
            )

        except Exception as e:
            logger.error(f"Error getting usage metrics: {e}")
            return UsageMetrics()

    async def get_usage_by_timeframe(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get usage data for a specific timeframe."""

        if not self.enabled or not self._redis_client:
            return []

        try:
            usage_data = []
            current_date = start_date

            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                daily_data = await self._redis_client.hgetall(f"usage:daily:{date_str}")

                if daily_data:
                    usage_data.append(
                        {
                            "date": date_str,
                            "requests": int(daily_data.get("requests", 0)),
                            "tokens": int(daily_data.get("tokens", 0)),
                            "cost_usd": float(daily_data.get("cost_usd", 0.0)),
                        }
                    )

                current_date += timedelta(days=1)

            return usage_data

        except Exception as e:
            logger.error(f"Error getting usage by timeframe: {e}")
            return []

    async def get_model_usage_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """Get usage breakdown by model."""

        if not self.enabled or not self._redis_client:
            return {}

        try:
            model_keys = await self._redis_client.keys("usage:model:*")
            model_breakdown = {}

            for key in model_keys:
                model = key.replace("usage:model:", "")
                model_data = await self._redis_client.hgetall(key)

                model_breakdown[model] = {
                    "requests": int(model_data.get("requests", 0)),
                    "tokens": int(model_data.get("tokens", 0)),
                    "cost_usd": float(model_data.get("cost_usd", 0.0)),
                }

            return model_breakdown

        except Exception as e:
            logger.error(f"Error getting model usage breakdown: {e}")
            return {}

    async def reset_metrics(self) -> bool:
        """Reset all usage metrics (use with caution)."""

        if not self.enabled or not self._redis_client:
            return False

        try:
            # Delete all usage-related keys
            keys_to_delete = []

            # Get all usage keys
            for pattern in ["usage:*", "alert:*"]:
                keys = await self._redis_client.keys(pattern)
                keys_to_delete.extend(keys)

            if keys_to_delete:
                await self._redis_client.delete(*keys_to_delete)

            logger.info(f"Reset {len(keys_to_delete)} usage tracking keys")
            return True

        except Exception as e:
            logger.error(f"Error resetting metrics: {e}")
            return False


# Global usage tracker instance
_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    """Get the global usage tracker instance."""
    global _usage_tracker

    if _usage_tracker is None:
        _usage_tracker = UsageTracker()

    return _usage_tracker


async def initialize_usage_tracker():
    """Initialize the usage tracker."""
    tracker = get_usage_tracker()
    await tracker.initialize()


async def cleanup_usage_tracker():
    """Cleanup the usage tracker."""
    global _usage_tracker
    if _usage_tracker:
        await _usage_tracker.cleanup()
        _usage_tracker = None
