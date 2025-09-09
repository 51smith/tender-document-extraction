from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse

from app.models.extraction import UsageMetrics
from app.services.usage_tracker import get_usage_tracker, UsageTracker
from app.services.gemini_service import get_gemini_client, GeminiClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["usage"])


@router.get("/usage", response_model=UsageMetrics)
async def get_current_usage(usage_tracker: UsageTracker = Depends(get_usage_tracker)):
    """
    Get current API usage metrics including tokens, costs, and rate limits.
    """
    try:
        metrics = await usage_tracker.get_usage_metrics()
        return metrics

    except Exception as e:
        logger.error(f"Error getting usage metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage metrics")


@router.get("/usage/detailed")
async def get_detailed_usage(
    usage_tracker: UsageTracker = Depends(get_usage_tracker),
    gemini_client: GeminiClient = Depends(get_gemini_client),
):
    """
    Get detailed usage information including rate limits and model breakdown.
    """
    try:
        # Get usage metrics
        metrics = await usage_tracker.get_usage_metrics()

        # Get model breakdown
        model_breakdown = await usage_tracker.get_model_usage_breakdown()

        # Get rate limit info
        rate_limit_info = gemini_client.get_usage_stats()

        return {
            "metrics": metrics,
            "model_breakdown": model_breakdown,
            "rate_limits": rate_limit_info,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting detailed usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve detailed usage")


@router.get("/usage/history")
async def get_usage_history(
    days: int = Query(default=7, ge=1, le=90, description="Number of days to retrieve"),
    usage_tracker: UsageTracker = Depends(get_usage_tracker),
):
    """
    Get usage history for the specified number of days.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        history = await usage_tracker.get_usage_by_timeframe(start_date, end_date)

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days,
            },
            "usage_history": history,
            "total_requests": sum(day.get("requests", 0) for day in history),
            "total_tokens": sum(day.get("tokens", 0) for day in history),
            "total_cost_usd": sum(day.get("cost_usd", 0.0) for day in history),
        }

    except Exception as e:
        logger.error(f"Error getting usage history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage history")


@router.get("/usage/models")
async def get_model_usage(usage_tracker: UsageTracker = Depends(get_usage_tracker)):
    """
    Get usage breakdown by AI model.
    """
    try:
        model_breakdown = await usage_tracker.get_model_usage_breakdown()

        # Calculate percentages
        total_requests = sum(data.get("requests", 0) for data in model_breakdown.values())
        total_tokens = sum(data.get("tokens", 0) for data in model_breakdown.values())
        total_cost = sum(data.get("cost_usd", 0.0) for data in model_breakdown.values())

        for model, data in model_breakdown.items():
            if total_requests > 0:
                data["request_percentage"] = (data.get("requests", 0) / total_requests) * 100
            else:
                data["request_percentage"] = 0.0

            if total_tokens > 0:
                data["token_percentage"] = (data.get("tokens", 0) / total_tokens) * 100
            else:
                data["token_percentage"] = 0.0

            if total_cost > 0:
                data["cost_percentage"] = (data.get("cost_usd", 0.0) / total_cost) * 100
            else:
                data["cost_percentage"] = 0.0

        return {
            "model_breakdown": model_breakdown,
            "totals": {"requests": total_requests, "tokens": total_tokens, "cost_usd": total_cost},
        }

    except Exception as e:
        logger.error(f"Error getting model usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve model usage")


@router.get("/usage/cost-analysis")
async def get_cost_analysis(
    days: int = Query(default=30, ge=1, le=90, description="Number of days to analyze"),
    usage_tracker: UsageTracker = Depends(get_usage_tracker),
):
    """
    Get cost analysis and projections.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        history = await usage_tracker.get_usage_by_timeframe(start_date, end_date)

        if not history:
            return {
                "analysis": "No usage data available for the specified period",
                "projections": {},
            }

        # Calculate statistics
        daily_costs = [day.get("cost_usd", 0.0) for day in history if day.get("cost_usd", 0.0) > 0]
        daily_requests = [day.get("requests", 0) for day in history if day.get("requests", 0) > 0]
        daily_tokens = [day.get("tokens", 0) for day in history if day.get("tokens", 0) > 0]

        total_cost = sum(daily_costs)
        avg_daily_cost = total_cost / len(daily_costs) if daily_costs else 0
        max_daily_cost = max(daily_costs) if daily_costs else 0
        min_daily_cost = min(daily_costs) if daily_costs else 0

        avg_cost_per_request = total_cost / sum(daily_requests) if sum(daily_requests) > 0 else 0
        avg_cost_per_1k_tokens = (
            (total_cost * 1000) / sum(daily_tokens) if sum(daily_tokens) > 0 else 0
        )

        # Simple projections
        monthly_projection = avg_daily_cost * 30
        yearly_projection = avg_daily_cost * 365

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days_analyzed": len(daily_costs),
            },
            "cost_analysis": {
                "total_cost_usd": total_cost,
                "average_daily_cost_usd": avg_daily_cost,
                "max_daily_cost_usd": max_daily_cost,
                "min_daily_cost_usd": min_daily_cost,
                "average_cost_per_request_usd": avg_cost_per_request,
                "average_cost_per_1k_tokens_usd": avg_cost_per_1k_tokens,
            },
            "projections": {
                "monthly_cost_usd": monthly_projection,
                "yearly_cost_usd": yearly_projection,
                "note": "Projections based on recent average daily usage",
            },
            "recommendations": _generate_cost_recommendations(avg_daily_cost, avg_cost_per_request),
        }

    except Exception as e:
        logger.error(f"Error getting cost analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cost analysis")


@router.post("/usage/reset")
async def reset_usage_metrics(
    confirm: bool = Query(False, description="Confirmation flag to reset metrics"),
    usage_tracker: UsageTracker = Depends(get_usage_tracker),
):
    """
    Reset usage metrics (use with caution - this deletes all usage history).
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Must set confirm=true to reset metrics")

    try:
        success = await usage_tracker.reset_metrics()

        if success:
            return {"message": "Usage metrics have been reset successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reset metrics")

    except Exception as e:
        logger.error(f"Error resetting usage metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset usage metrics")


def _generate_cost_recommendations(avg_daily_cost: float, avg_cost_per_request: float) -> List[str]:
    """Generate cost optimization recommendations."""
    recommendations = []

    if avg_daily_cost > 10.0:
        recommendations.append("Consider implementing more aggressive caching to reduce API calls")
        recommendations.append("Review document preprocessing to minimize token usage")

    if avg_cost_per_request > 0.50:
        recommendations.append(
            "High per-request cost detected - consider optimizing prompt templates"
        )
        recommendations.append("Evaluate using Gemini Flash model for simpler documents")

    if avg_daily_cost > 50.0:
        recommendations.append("Consider implementing cost budgets and alerts")
        recommendations.append("Review batch processing efficiency")

    if not recommendations:
        recommendations.append("Current usage appears cost-efficient")
        recommendations.append("Continue monitoring for optimization opportunities")

    return recommendations
