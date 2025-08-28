"""
Focused tests for Health Router missing coverage lines.
Targets specific lines: 60-62, 68, 80-82, 89, 116-118, 136, 170, 175
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.services.gemini_service import get_gemini_client
from app.services.job_manager import get_job_manager
from app.utils.prompt_builder import get_prompt_builder
from main import app


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client."""
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock()
    mock.test_connection = AsyncMock(return_value={"status": "success", "model": "gemini-2.5-pro"})
    mock.get_usage_stats = MagicMock(return_value={"requests_today": 100, "tokens_used": 5000})
    return mock


@pytest.fixture
def mock_job_manager():
    """Mock job manager."""
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock()
    mock.get_job_statistics = AsyncMock(return_value={"total_jobs": 100, "active_jobs": 5})
    return mock


@pytest.fixture
def mock_prompt_builder():
    """Mock prompt builder."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.get_available_templates = MagicMock(return_value=["default", "custom"])
    return mock


@pytest.fixture
def test_client():
    """Test client with dependency overrides."""
    return TestClient(app)


class TestHealthRouterCoverage:
    """Tests targeting specific missing coverage lines."""

    def test_detailed_health_llm_exception_lines_60_62(
        self, test_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test lines 60-62: LLM exception handling in detailed health check."""
        # Setup mocks
        from unittest.mock import AsyncMock

        mock_gemini_client.test_connection = AsyncMock(side_effect=Exception("Connection failed"))

        app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client
        app.dependency_overrides[get_job_manager] = lambda: mock_job_manager
        app.dependency_overrides[get_prompt_builder] = lambda: mock_prompt_builder

        try:
            response = test_client.get("/health/detailed")

            # Lines 60-62: exception handling in LLM check
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["services"]["llm_provider"]["status"] == "unhealthy"
            assert "error" in data["services"]["llm_provider"]
        finally:
            app.dependency_overrides.clear()

    def test_detailed_health_redis_success_line_68(
        self, test_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test line 68: Redis success path in detailed health check."""
        app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client
        app.dependency_overrides[get_job_manager] = lambda: mock_job_manager
        app.dependency_overrides[get_prompt_builder] = lambda: mock_prompt_builder

        try:
            response = test_client.get("/health/detailed")

            # Line 68: Redis success path
            assert response.status_code == 200
            data = response.json()
            assert data["services"]["redis"]["status"] == "healthy"
        finally:
            app.dependency_overrides.clear()

    def test_detailed_health_redis_exception_lines_69_71(
        self, test_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test lines 69-71: Redis exception handling in detailed health check."""
        # Setup Redis exception
        from unittest.mock import AsyncMock

        mock_job_manager.get_job_statistics = AsyncMock(
            side_effect=Exception("Redis connection failed")
        )

        app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client
        app.dependency_overrides[get_job_manager] = lambda: mock_job_manager
        app.dependency_overrides[get_prompt_builder] = lambda: mock_prompt_builder

        try:
            response = test_client.get("/health/detailed")

            # Lines 69-71: Redis exception handling
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["services"]["redis"]["status"] == "unhealthy"
            assert "Redis connection failed" in data["services"]["redis"]["error"]
        finally:
            app.dependency_overrides.clear()

    def test_detailed_health_prompt_builder_exception_lines_80_82(
        self, test_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test lines 80-82: Prompt builder exception handling."""
        # Setup exception - prompt_builder methods are synchronous
        from unittest.mock import MagicMock

        mock_prompt_builder.get_available_templates = MagicMock(
            side_effect=Exception("Templates failed")
        )

        app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client
        app.dependency_overrides[get_job_manager] = lambda: mock_job_manager
        app.dependency_overrides[get_prompt_builder] = lambda: mock_prompt_builder

        try:
            response = test_client.get("/health/detailed")

            # Lines 80-82: prompt builder exception handling
            assert response.status_code == 503
            data = response.json()
            assert data["services"]["prompt_builder"]["status"] == "unhealthy"
            assert "error" in data["services"]["prompt_builder"]
        finally:
            app.dependency_overrides.clear()

    def test_detailed_health_success_line_89(
        self, test_client, mock_gemini_client, mock_job_manager, mock_prompt_builder
    ):
        """Test line 89: All services healthy return path."""
        app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client
        app.dependency_overrides[get_job_manager] = lambda: mock_job_manager
        app.dependency_overrides[get_prompt_builder] = lambda: mock_prompt_builder

        try:
            response = test_client.get("/health/detailed")

            # Line 89: healthy return path
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
        finally:
            app.dependency_overrides.clear()

    def test_llm_health_exception_lines_116_118(self, test_client, mock_gemini_client):
        """Test lines 116-118: LLM health check exception handling."""
        # Setup exception
        mock_gemini_client.test_connection = AsyncMock(side_effect=Exception("API timeout"))

        app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client

        try:
            response = test_client.get("/health/llm")

            # Lines 116-118: LLM health exception
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "API timeout" in data["error"]
        finally:
            app.dependency_overrides.clear()

    def test_redis_health_success_line_136(self, test_client, mock_job_manager):
        """Test line 136: Redis health success return."""
        app.dependency_overrides[get_job_manager] = lambda: mock_job_manager

        try:
            response = test_client.get("/health/redis")

            # Line 136: Redis health success
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "statistics" in data
        finally:
            app.dependency_overrides.clear()

    def test_readiness_exception_line_170(self, test_client, mock_gemini_client, mock_job_manager):
        """Test line 170: Readiness check exception handling."""
        # Setup exception
        mock_gemini_client.get_usage_stats = AsyncMock(side_effect=Exception("LLM not ready"))

        app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client
        app.dependency_overrides[get_job_manager] = lambda: mock_job_manager

        try:
            response = test_client.get("/ready")

            # Line 170: readiness exception handling
            assert response.status_code == 503
            data = response.json()
            assert "not ready" in data["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_readiness_success_line_175(self, test_client, mock_gemini_client, mock_job_manager):
        """Test line 175: Readiness check success return."""
        app.dependency_overrides[get_gemini_client] = lambda: mock_gemini_client
        app.dependency_overrides[get_job_manager] = lambda: mock_job_manager

        try:
            response = test_client.get("/ready")

            # Line 175: readiness success
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
        finally:
            app.dependency_overrides.clear()

    def test_basic_health_endpoint_line_23(self, test_client):
        """Test line 23: Basic health endpoint return."""
        try:
            response = test_client.get("/health")

            # Line 23: basic health endpoint
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data
            assert "version" in data
        finally:
            app.dependency_overrides.clear()

    def test_liveness_endpoint_lines_189_201(self, test_client):
        """Test lines 189-201: Liveness check paths."""
        try:
            response = test_client.get("/live")

            # Lines 189-201: liveness check
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "alive"
            assert "timestamp" in data
        finally:
            app.dependency_overrides.clear()
