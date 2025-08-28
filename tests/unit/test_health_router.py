"""Tests for the health router endpoints."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from main import app
from app.config import settings
from app.services.gemini_service import get_gemini_client
from app.services.job_manager import get_job_manager 
from app.utils.prompt_builder import get_prompt_builder


# Use the sync_client fixture from conftest.py


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client fixture."""
    mock = AsyncMock()
    mock.test_connection = AsyncMock(return_value={"status": "success", "model": "gemini-2.5-pro"})
    mock.get_usage_stats = AsyncMock(return_value={"requests_today": 100, "tokens_used": 5000})
    return mock


@pytest.fixture
def mock_job_manager():
    """Mock job manager fixture."""
    mock = AsyncMock()
    mock.get_job_statistics = AsyncMock(return_value={"total_jobs": 100, "active_jobs": 5})
    return mock


@pytest.fixture
def mock_prompt_builder():
    """Mock prompt builder fixture."""
    mock = AsyncMock()
    mock.get_available_templates = AsyncMock(return_value=["default", "custom"])
    return mock


@pytest.fixture
def override_dependencies(sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder):
    """Override FastAPI dependencies for health router tests."""
    app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client
    app.dependency_overrides[get_job_manager] = lambda: mock_job_manager
    app.dependency_overrides[get_prompt_builder] = lambda: mock_prompt_builder
    yield
    # Cleanup
    app.dependency_overrides.clear()


class TestBasicHealthCheck:
    """Tests for basic health check endpoint."""

    def test_health_check_success(self, sync_client):
        """Test basic health check returns success."""
        response = sync_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"
        assert data["environment"] == settings.environment

    def test_health_check_structure(self, sync_client):
        """Test health check response structure."""
        response = sync_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["status", "timestamp", "version", "environment"]
        for field in required_fields:
            assert field in data

    def test_health_check_timestamp_format(self, sync_client):
        """Test health check timestamp is in ISO format."""
        response = sync_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify timestamp is in ISO format (ends with Z)
        timestamp = data["timestamp"]
        assert timestamp.endswith("Z") or "T" in timestamp


class TestDetailedHealthCheck:
    """Tests for detailed health check endpoint."""

    def test_detailed_health_all_services_healthy(
        self, override_dependencies, sync_client
    ):
        """Test detailed health check when all services are healthy (line 89 - healthy path)."""
        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert - This should hit line 89 (healthy return path)
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "services" in data
        assert data["services"]["llm_provider"]["status"] == "healthy"
        assert data["services"]["redis"]["status"] == "healthy"
        assert data["services"]["prompt_builder"]["status"] == "healthy"
        
        # Check LLM provider service
        assert data["services"]["llm_provider"]["status"] == "healthy"
        assert data["services"]["llm_provider"]["details"]["status"] == "success"
        
        # Check Redis service (line 68 - Redis success path)
        assert data["services"]["redis"]["status"] == "healthy"
        assert "details" in data["services"]["redis"]
        
        # Check prompt builder service
        assert data["services"]["prompt_builder"]["status"] == "healthy"
        assert "available_templates" in data["services"]["prompt_builder"]


class TestHealthCheckErrorHandling:
    """Test health check error handling scenarios."""
    
    def test_detailed_health_llm_exception(
        self, override_dependencies, sync_client, mock_gemini_client
    ):
        """Test detailed health check when LLM service throws exception (lines 60-62)."""
        # Setup - LLM service throws exception (targets lines 60-62)
        mock_gemini_client.test_connection = AsyncMock(side_effect=Exception("LLM service connection failed"))
        
        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert
        assert response.status_code == 503  # Service Unavailable when unhealthy
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["llm_provider"]["status"] == "unhealthy"
        assert "LLM service connection failed" in data["services"]["llm_provider"]["error"]
        
    @patch("app.routers.health.get_gemini_client") 
    @patch("app.routers.health.get_job_manager")
    @patch("app.routers.health.get_prompt_builder")
    def test_detailed_health_redis_exception(
        self, mock_get_prompt_builder, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test detailed health check when Redis/Job Manager throws exception (line 68)."""
        # Setup - Redis/Job manager throws exception
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        mock_get_prompt_builder.return_value = mock_prompt_builder
        
        mock_gemini_client.test_connection.return_value = {"status": "success"}
        mock_job_manager.get_job_statistics = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_prompt_builder.get_available_templates.return_value = ["default"]
        
        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["redis"]["status"] == "unhealthy"
        assert "Redis connection failed" in data["services"]["redis"]["error"]
        
    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    @patch("app.routers.health.get_prompt_builder")
    def test_detailed_health_prompt_builder_exception(
        self, mock_get_prompt_builder, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test detailed health check when Prompt Builder throws exception (lines 80-82)."""
        # Setup - Prompt builder throws exception
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        mock_get_prompt_builder.return_value = mock_prompt_builder
        
        mock_gemini_client.test_connection.return_value = {"status": "success"}
        mock_job_manager.get_job_statistics.return_value = {"total_jobs": 100}
        mock_prompt_builder.get_available_templates = AsyncMock(side_effect=Exception("Template loading failed"))
        
        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert 
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["prompt_builder"]["status"] == "unhealthy"
        assert "Template loading failed" in data["services"]["prompt_builder"]["error"]
        
    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    @patch("app.routers.health.get_prompt_builder")
    def test_detailed_health_multiple_failures(
        self, mock_get_prompt_builder, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test detailed health check when multiple services fail."""
        # Setup - Multiple service failures
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        mock_get_prompt_builder.return_value = mock_prompt_builder
        
        mock_gemini_client.test_connection = AsyncMock(side_effect=Exception("LLM failed"))
        mock_job_manager.get_job_statistics = AsyncMock(side_effect=Exception("Redis failed")) 
        mock_prompt_builder.get_available_templates = AsyncMock(side_effect=Exception("Templates failed"))
        
        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["llm_provider"]["status"] == "unhealthy"
        assert data["services"]["redis"]["status"] == "unhealthy"
        assert data["services"]["prompt_builder"]["status"] == "unhealthy"
        
    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager") 
    @patch("app.routers.health.get_prompt_builder")
    def test_detailed_health_llm_unhealthy_status(
        self, mock_get_prompt_builder, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test when LLM returns unhealthy status (not exception) - line 89."""
        # Setup - LLM returns unhealthy status (not an exception)
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        mock_get_prompt_builder.return_value = mock_prompt_builder
        
        mock_gemini_client.test_connection.return_value = {"status": "error", "error": "API key invalid"}
        mock_job_manager.get_job_statistics.return_value = {"total_jobs": 100}
        mock_prompt_builder.get_available_templates.return_value = ["default"]
        
        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        # Should still show the LLM service details even when status != success

    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    @patch("app.routers.health.get_prompt_builder")
    def test_detailed_health_llm_unhealthy(
        self, mock_get_prompt_builder, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test detailed health check when LLM service is unhealthy."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        mock_get_prompt_builder.return_value = mock_prompt_builder
        
        mock_gemini_client.test_connection.return_value = {"status": "failed", "error": "API key invalid"}
        mock_job_manager.get_job_statistics.return_value = {"total_jobs": 100}
        mock_prompt_builder.get_available_templates.return_value = ["default"]

        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert
        assert response.status_code == 503  # Service unavailable
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["llm_provider"]["status"] == "unhealthy"
        assert data["services"]["redis"]["status"] == "healthy"
        assert data["services"]["prompt_builder"]["status"] == "healthy"

    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    @patch("app.routers.health.get_prompt_builder")
    def test_detailed_health_redis_unhealthy(
        self, mock_get_prompt_builder, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test detailed health check when Redis service is unhealthy."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        mock_get_prompt_builder.return_value = mock_prompt_builder
        
        mock_gemini_client.test_connection.return_value = {"status": "success"}
        mock_job_manager.get_job_statistics = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_prompt_builder.get_available_templates.return_value = ["default"]

        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["llm_provider"]["status"] == "healthy"
        assert data["services"]["redis"]["status"] == "unhealthy"
        assert "Redis connection failed" in data["services"]["redis"]["error"]

    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager") 
    @patch("app.routers.health.get_prompt_builder")
    def test_detailed_health_prompt_builder_unhealthy(
        self, mock_get_prompt_builder, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test detailed health check when prompt builder service is unhealthy."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        mock_get_prompt_builder.return_value = mock_prompt_builder
        
        mock_gemini_client.test_connection.return_value = {"status": "success"}
        mock_job_manager.get_job_statistics.return_value = {"total_jobs": 100}
        mock_prompt_builder.get_available_templates = AsyncMock(side_effect=Exception("Template loading failed"))

        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["prompt_builder"]["status"] == "unhealthy"
        assert "Template loading failed" in data["services"]["prompt_builder"]["error"]

    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    @patch("app.routers.health.get_prompt_builder")
    def test_detailed_health_multiple_services_unhealthy(
        self, mock_get_prompt_builder, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test detailed health check when multiple services are unhealthy."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        mock_get_prompt_builder.return_value = mock_prompt_builder
        
        mock_gemini_client.test_connection = AsyncMock(side_effect=Exception("LLM service down"))
        mock_job_manager.get_job_statistics = AsyncMock(side_effect=Exception("Redis down"))
        mock_prompt_builder.get_available_templates = AsyncMock(side_effect=Exception("Templates unavailable"))

        # Execute
        response = sync_client.get("/health/detailed")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["llm_provider"]["status"] == "unhealthy"
        assert data["services"]["redis"]["status"] == "unhealthy"
        assert data["services"]["prompt_builder"]["status"] == "unhealthy"


class TestLLMHealthCheck:
    """Tests for LLM-specific health check endpoint."""

    @patch("app.routers.health.get_gemini_client")
    def test_llm_health_check_success(self, mock_get_gemini_client, sync_client, mock_gemini_client):
        """Test LLM health check success."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_gemini_client.test_connection.return_value = {
            "status": "success",
            "model": "gemini-2.5-pro",
            "latency_ms": 150
        }
        mock_gemini_client.get_usage_stats.return_value = {
            "requests_per_minute": 45,
            "tokens_per_minute": 12000,
            "quota_remaining": "85%"
        }
        
        # Execute
        with patch("app.config.settings.llm_provider", "gemini"):
            response = sync_client.get("/health/llm")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["connection_test"]["status"] == "success"
        assert "usage_stats" in data
        assert "timestamp" in data

    @patch("app.routers.health.get_gemini_client")
    def test_llm_health_check_non_gemini_provider(self, mock_get_gemini_client, sync_client, mock_gemini_client):
        """Test LLM health check with non-Gemini provider (no usage stats)."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_gemini_client.test_connection.return_value = {"status": "success", "model": "ollama-llama"}
        
        # Execute
        with patch("app.config.settings.llm_provider", "ollama"):
            response = sync_client.get("/health/llm")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["connection_test"]["status"] == "success"
        assert "usage_stats" not in data  # Should not include usage stats for non-Gemini

    @patch("app.routers.health.get_gemini_client")
    def test_llm_health_check_failure(self, mock_get_gemini_client, sync_client, mock_gemini_client):
        """Test LLM health check failure."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_gemini_client.test_connection.return_value = {
            "status": "error",
            "error": "Authentication failed"
        }
        
        # Execute
        response = sync_client.get("/health/llm")
        
        # Assert
        assert response.status_code == 200  # Still returns 200 but with unhealthy status
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["connection_test"]["status"] == "error"

    @patch("app.routers.health.get_gemini_client")
    def test_llm_health_check_exception(self, mock_get_gemini_client, sync_client, mock_gemini_client):
        """Test LLM health check with exception (lines 116-125)."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_gemini_client.test_connection = AsyncMock(side_effect=Exception("Connection timeout"))
        
        # Execute
        response = sync_client.get("/health/llm")
        
        # Assert - This should hit lines 116-125 (exception handling in LLM health check)
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert "Connection timeout" in data["error"]
        assert "timestamp" in data


class TestRedisHealthCheck:
    """Tests for Redis-specific health check endpoint."""

    @patch("app.routers.health.get_job_manager")
    def test_redis_health_check_success(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test Redis health check success (lines 136-140)."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job_statistics = AsyncMock(return_value={
            "total_jobs": 150,
            "active_jobs": 10,
            "completed_jobs": 140,
            "failed_jobs": 0
        })
        
        # Execute
        response = sync_client.get("/health/redis")
        
        # Assert - This should hit lines 136-140 (Redis success path)
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "statistics" in data
        assert data["statistics"]["total_jobs"] == 150
        assert "timestamp" in data

    @patch("app.routers.health.get_job_manager")
    def test_redis_health_check_failure(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test Redis health check failure."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job_statistics = AsyncMock(side_effect=Exception("Redis connection refused"))
        
        # Execute
        response = sync_client.get("/health/redis")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert "Redis connection refused" in data["error"]
        assert "timestamp" in data

    @patch("app.routers.health.get_job_manager")
    def test_redis_health_check_empty_statistics(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test Redis health check with empty statistics."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job_statistics = AsyncMock(return_value={})
        
        # Execute
        response = sync_client.get("/health/redis")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["statistics"] == {}


class TestReadinessCheck:
    """Tests for Kubernetes readiness probe endpoint."""

    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    def test_readiness_check_success(
        self, mock_get_job_manager, mock_get_gemini_client, 
        sync_client, mock_gemini_client, mock_job_manager
    ):
        """Test readiness check when all dependencies are ready (line 175)."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        
        mock_gemini_client.get_usage_stats.return_value = {"initialized": True}
        mock_job_manager.get_job_statistics = AsyncMock(return_value={"total_jobs": 50})
        
        # Execute
        response = sync_client.get("/ready")
        
        # Assert - This should hit line 175 (readiness success return)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    def test_readiness_check_llm_not_ready(
        self, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager
    ):
        """Test readiness check when LLM client is not ready (line 170)."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        
        mock_gemini_client.get_usage_stats.return_value = None  # Not initialized
        mock_job_manager.get_job_statistics = AsyncMock(return_value={"total_jobs": 50})
        
        # Execute
        response = sync_client.get("/ready")
        
        # Assert - This should hit line 170 (LLM client not initialized exception)
        assert response.status_code == 503
        data = response.json()
        assert "not ready" in data["detail"]

    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    def test_readiness_check_redis_not_ready(
        self, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager
    ):
        """Test readiness check when Redis is not ready."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        
        mock_gemini_client.get_usage_stats.return_value = {"initialized": True}
        mock_job_manager.get_job_statistics = AsyncMock(side_effect=Exception("Redis not available"))
        
        # Execute
        response = sync_client.get("/ready")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        assert "not ready" in data["detail"]

    @patch("app.routers.health.get_gemini_client")
    @patch("app.routers.health.get_job_manager")
    def test_readiness_check_multiple_failures(
        self, mock_get_job_manager, mock_get_gemini_client,
        sync_client, mock_gemini_client, mock_job_manager
    ):
        """Test readiness check with multiple dependency failures."""
        # Setup
        mock_get_gemini_client.return_value = mock_gemini_client
        mock_get_job_manager.return_value = mock_job_manager
        
        mock_gemini_client.get_usage_stats.side_effect = Exception("LLM not ready")
        mock_job_manager.get_job_statistics.side_effect = Exception("Redis not ready")
        
        # Execute
        response = sync_client.get("/ready")
        
        # Assert
        assert response.status_code == 503


class TestLivenessCheck:
    """Tests for Kubernetes liveness probe endpoint."""

    def test_liveness_check_success(self, sync_client):
        """Test liveness check success."""
        response = sync_client.get("/live")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "alive"
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))

    def test_liveness_check_structure(self, sync_client):
        """Test liveness check response structure."""
        response = sync_client.get("/live")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["status", "timestamp", "uptime_seconds"]
        for field in required_fields:
            assert field in data

    def test_liveness_check_timestamp_format(self, sync_client):
        """Test liveness check timestamp format."""
        response = sync_client.get("/live")
        
        assert response.status_code == 200
        data = response.json()
        
        timestamp = data["timestamp"]
        assert "T" in timestamp  # ISO format should contain T

    @patch("app.routers.health.datetime")
    def test_liveness_check_exception_handling(self, mock_datetime, sync_client):
        """Test liveness check exception handling."""
        # Setup - make datetime.utcnow() raise an exception
        mock_datetime.utcnow.side_effect = Exception("Time service failed")
        
        # Execute
        response = sync_client.get("/live")
        
        # Assert
        assert response.status_code == 503
        data = response.json()
        assert "not alive" in data["detail"]


class TestHealthCheckIntegration:
    """Integration tests for health check endpoints."""

    def test_all_health_endpoints_accessible(self, sync_client):
        """Test that all health endpoints are accessible."""
        endpoints = ["/health", "/live"]
        
        for endpoint in endpoints:
            response = sync_client.get(endpoint)
            assert response.status_code in [200, 503], f"Endpoint {endpoint} not accessible"

    def test_health_endpoints_content_type(self, sync_client):
        """Test that health endpoints return JSON."""
        endpoints = ["/health", "/live"]
        
        for endpoint in endpoints:
            response = sync_client.get(endpoint)
            assert "application/json" in response.headers.get("content-type", "")

    def test_health_check_consistency(self, sync_client):
        """Test that multiple calls to health endpoints are consistent."""
        # Make multiple calls
        responses = [sync_client.get("/health") for _ in range(3)]
        
        # All should have same status code
        status_codes = [r.status_code for r in responses]
        assert len(set(status_codes)) == 1, "Health check responses inconsistent"
        
        # All should have same status field
        statuses = [r.json()["status"] for r in responses]
        assert len(set(statuses)) == 1, "Health status inconsistent"