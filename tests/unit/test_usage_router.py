"""Tests for the usage router endpoints."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.models.extraction import UsageMetrics
from main import app


@pytest.fixture
def mock_usage_tracker():
    """Mock usage tracker fixture."""
    return AsyncMock()


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client fixture."""
    return AsyncMock()


@pytest.fixture
def sample_usage_metrics():
    """Sample usage metrics for testing."""
    return UsageMetrics(
        total_requests=150,
        total_tokens=45000,
        total_cost_usd=12.50,
        requests_today=25,
        tokens_today=7500,
        cost_today_usd=2.10,
        average_tokens_per_request=300,
        rate_limit_remaining_rpm=280,
        rate_limit_remaining_tpm=48000,
        last_request_timestamp="2024-01-01T12:00:00Z",
    )


@pytest.fixture
def sample_model_breakdown():
    """Sample model usage breakdown for testing."""
    return {
        "gemini-2.5-pro": {
            "requests": 100,
            "tokens": 35000,
            "cost_usd": 10.50,
            "average_tokens_per_request": 350,
        },
        "gemini-1.5-flash": {
            "requests": 50,
            "tokens": 10000,
            "cost_usd": 2.00,
            "average_tokens_per_request": 200,
        },
    }


@pytest.fixture
def sample_usage_history():
    """Sample usage history for testing."""
    base_date = datetime.now() - timedelta(days=7)
    return [
        {
            "date": (base_date + timedelta(days=i)).isoformat(),
            "requests": 20 + i * 5,
            "tokens": 5000 + i * 1000,
            "cost_usd": 1.5 + i * 0.3,
        }
        for i in range(7)
    ]


class TestCurrentUsage:
    """Tests for current usage endpoint."""

    def test_get_current_usage_success(self, sync_client, mock_usage_tracker, sample_usage_metrics):
        """Test successful current usage retrieval."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.get_usage_metrics.return_value = sample_usage_metrics

        try:
            response = sync_client.get("/api/v1/usage")
            assert response.status_code == 200
            data = response.json()

            assert data["total_requests"] == 150
            assert data["total_tokens"] == 45000
            assert data["total_cost_usd"] == 12.50
            assert data["requests_today"] == 25
            assert data["tokens_today"] == 7500

        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]

    def test_get_current_usage_error(self, sync_client, mock_usage_tracker):
        """Test current usage retrieval with error."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.get_usage_metrics.side_effect = Exception("Database error")

        try:
            response = sync_client.get("/api/v1/usage")
            assert response.status_code == 500
            data = response.json()
            assert "Failed to retrieve usage metrics" in data["detail"]
        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]


class TestModelUsage:
    """Tests for model usage endpoint."""

    def test_get_model_usage_success(self, sync_client, mock_usage_tracker, sample_model_breakdown):
        """Test successful model usage retrieval."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.get_model_usage_breakdown.return_value = sample_model_breakdown

        try:
            response = sync_client.get("/api/v1/usage/models")
            assert response.status_code == 200
            data = response.json()

            assert "model_breakdown" in data
            assert "totals" in data

            # Check model breakdown with percentages
            breakdown = data["model_breakdown"]
            assert "gemini-2.5-pro" in breakdown
            assert "request_percentage" in breakdown["gemini-2.5-pro"]
            assert "token_percentage" in breakdown["gemini-2.5-pro"]
            assert "cost_percentage" in breakdown["gemini-2.5-pro"]

            # Check totals
            totals = data["totals"]
            assert totals["requests"] == 150
            assert totals["tokens"] == 45000
            assert totals["cost_usd"] == 12.5

        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]

    def test_get_model_usage_empty(self, sync_client, mock_usage_tracker):
        """Test model usage with empty breakdown."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.get_model_usage_breakdown.return_value = {}

        try:
            response = sync_client.get("/api/v1/usage/models")
            assert response.status_code == 200
            data = response.json()

            assert data["model_breakdown"] == {}
            assert data["totals"]["requests"] == 0
            assert data["totals"]["tokens"] == 0
            assert data["totals"]["cost_usd"] == 0
        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]


class TestUsageHistory:
    """Tests for usage history endpoint."""

    def test_get_usage_history_default(self, sync_client, mock_usage_tracker, sample_usage_history):
        """Test usage history with default parameters."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.get_usage_by_timeframe.return_value = sample_usage_history

        try:
            response = sync_client.get("/api/v1/usage/history")
            assert response.status_code == 200
            data = response.json()

            assert data["period"]["days"] == 7
            assert "usage_history" in data
            assert "total_requests" in data
            assert "total_tokens" in data
            assert "total_cost_usd" in data

            # Verify totals calculation
            expected_requests = sum(day["requests"] for day in sample_usage_history)
            assert data["total_requests"] == expected_requests

        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]

    def test_get_usage_history_invalid_days(self, sync_client):
        """Test usage history with invalid days parameter."""
        # Test days too small
        response = sync_client.get("/api/v1/usage/history?days=0")
        assert response.status_code == 422

        # Test days too large
        response = sync_client.get("/api/v1/usage/history?days=100")
        assert response.status_code == 422


class TestUsageReset:
    """Tests for usage reset endpoint."""

    def test_reset_usage_metrics_success(self, sync_client, mock_usage_tracker):
        """Test successful usage metrics reset."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.reset_metrics.return_value = True

        try:
            response = sync_client.post("/api/v1/usage/reset?confirm=true")
            assert response.status_code == 200
            data = response.json()
            assert "successfully" in data["message"]
        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]

    def test_reset_usage_metrics_no_confirmation(self, sync_client, mock_usage_tracker):
        """Test usage reset without confirmation."""
        response = sync_client.post("/api/v1/usage/reset")
        assert response.status_code == 400
        data = response.json()
        assert "confirm=true" in data["detail"]


class TestDetailedUsage:
    """Tests for detailed usage endpoint."""

    def test_get_detailed_usage_success(
        self,
        sync_client,
        mock_usage_tracker,
        mock_gemini_client,
        sample_usage_metrics,
        sample_model_breakdown,
    ):
        """Test successful detailed usage retrieval."""
        from app.services.gemini_service import get_gemini_client
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        def mock_get_gemini_client_override():
            return mock_gemini_client

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        app.dependency_overrides[get_gemini_client] = mock_get_gemini_client_override

        mock_usage_tracker.get_usage_metrics = AsyncMock(return_value=sample_usage_metrics)
        mock_usage_tracker.get_model_usage_breakdown = AsyncMock(
            return_value=sample_model_breakdown
        )
        mock_gemini_client.get_usage_stats = AsyncMock(
            return_value={
                "requests_per_minute": 45,
                "tokens_per_minute": 12000,
                "quota_remaining": "85%",
            }
        )

        try:
            response = sync_client.get("/api/v1/usage/detailed")
            assert response.status_code == 200
            data = response.json()

            assert "metrics" in data
            assert "model_breakdown" in data
            assert "rate_limits" in data
            assert "timestamp" in data

            assert data["metrics"]["total_requests"] == 150
            assert "gemini-2.5-pro" in data["model_breakdown"]
            assert data["rate_limits"]["requests_per_minute"] == 45
        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]
            if get_gemini_client in app.dependency_overrides:
                del app.dependency_overrides[get_gemini_client]

    def test_get_detailed_usage_error(self, sync_client, mock_usage_tracker, mock_gemini_client):
        """Test detailed usage with error."""
        from app.services.gemini_service import get_gemini_client
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        def mock_get_gemini_client_override():
            return mock_gemini_client

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        app.dependency_overrides[get_gemini_client] = mock_get_gemini_client_override

        mock_usage_tracker.get_usage_metrics.side_effect = Exception("Tracker error")

        try:
            response = sync_client.get("/api/v1/usage/detailed")
            assert response.status_code == 500
            data = response.json()
            assert "Failed to retrieve detailed usage" in data["detail"]
        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]
            if get_gemini_client in app.dependency_overrides:
                del app.dependency_overrides[get_gemini_client]


class TestCostAnalysis:
    """Tests for cost analysis endpoint."""

    def test_get_cost_analysis_success(self, sync_client, mock_usage_tracker, sample_usage_history):
        """Test successful cost analysis."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.get_usage_by_timeframe.return_value = sample_usage_history

        try:
            response = sync_client.get("/api/v1/usage/cost-analysis")
            assert response.status_code == 200
            data = response.json()

            assert "period" in data
            assert "cost_analysis" in data
            assert "projections" in data
            assert "recommendations" in data

            # Check cost analysis fields
            cost_analysis = data["cost_analysis"]
            assert "total_cost_usd" in cost_analysis
            assert "average_daily_cost_usd" in cost_analysis
            assert "max_daily_cost_usd" in cost_analysis
            assert "min_daily_cost_usd" in cost_analysis
            assert "average_cost_per_request_usd" in cost_analysis
            assert "average_cost_per_1k_tokens_usd" in cost_analysis

            # Check projections
            projections = data["projections"]
            assert "monthly_cost_usd" in projections
            assert "yearly_cost_usd" in projections
            assert "note" in projections
        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]

    def test_get_cost_analysis_no_data(self, sync_client, mock_usage_tracker):
        """Test cost analysis with no usage data."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.get_usage_by_timeframe.return_value = []

        try:
            response = sync_client.get("/api/v1/usage/cost-analysis")
            assert response.status_code == 200
            data = response.json()

            assert "No usage data available" in data["analysis"]
            assert data["projections"] == {}
        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]

    def test_get_cost_analysis_custom_days(
        self, sync_client, mock_usage_tracker, sample_usage_history
    ):
        """Test cost analysis with custom days parameter."""
        from app.services.usage_tracker import get_usage_tracker

        def mock_get_usage_tracker_override():
            return mock_usage_tracker

        app.dependency_overrides[get_usage_tracker] = mock_get_usage_tracker_override
        mock_usage_tracker.get_usage_by_timeframe.return_value = sample_usage_history

        try:
            response = sync_client.get("/api/v1/usage/cost-analysis?days=60")
            assert response.status_code == 200
            data = response.json()
            assert data["period"]["days_analyzed"] == 7  # Based on sample_usage_history length

            # Verify timeframe call
            call_args = mock_usage_tracker.get_usage_by_timeframe.call_args[0]
            start_date, end_date = call_args
            assert (end_date - start_date).days == 60
        finally:
            if get_usage_tracker in app.dependency_overrides:
                del app.dependency_overrides[get_usage_tracker]

    def test_get_cost_analysis_invalid_days(self, sync_client):
        """Test cost analysis with invalid days parameter."""
        # Test days too small
        response = sync_client.get("/api/v1/usage/cost-analysis?days=0")
        assert response.status_code == 422

        # Test days too large
        response = sync_client.get("/api/v1/usage/cost-analysis?days=100")
        assert response.status_code == 422


class TestCostRecommendations:
    """Tests for cost recommendations function."""

    def test_generate_cost_recommendations_low_cost(self):
        """Test recommendations for low cost usage."""
        from app.routers.usage import _generate_cost_recommendations

        recommendations = _generate_cost_recommendations(
            avg_daily_cost=2.0, avg_cost_per_request=0.1
        )

        assert "cost-efficient" in " ".join(recommendations)
        assert "Continue monitoring" in " ".join(recommendations)

    def test_generate_cost_recommendations_high_daily_cost(self):
        """Test recommendations for high daily cost."""
        from app.routers.usage import _generate_cost_recommendations

        recommendations = _generate_cost_recommendations(
            avg_daily_cost=15.0, avg_cost_per_request=0.2
        )

        recommendation_text = " ".join(recommendations)
        assert "caching" in recommendation_text
        assert "preprocessing" in recommendation_text

    def test_generate_cost_recommendations_high_per_request_cost(self):
        """Test recommendations for high per-request cost."""
        from app.routers.usage import _generate_cost_recommendations

        recommendations = _generate_cost_recommendations(
            avg_daily_cost=5.0, avg_cost_per_request=0.75
        )

        recommendation_text = " ".join(recommendations)
        assert "prompt templates" in recommendation_text
        assert "Flash model" in recommendation_text

    def test_generate_cost_recommendations_very_high_cost(self):
        """Test recommendations for very high cost."""
        from app.routers.usage import _generate_cost_recommendations

        recommendations = _generate_cost_recommendations(
            avg_daily_cost=60.0, avg_cost_per_request=0.8
        )

        recommendation_text = " ".join(recommendations)
        assert "budgets and alerts" in recommendation_text
        assert "batch processing" in recommendation_text
