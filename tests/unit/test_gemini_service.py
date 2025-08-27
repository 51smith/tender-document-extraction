import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    GeminiAPIException,
    GeminiModelError,
    GeminiQuotaExceededError,
    GeminiRateLimitError,
)
from app.services.gemini_service import GeminiClient, get_gemini_client, reset_gemini_client


class TestGeminiService:
    """Test Gemini API service functionality."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup method to reset client before each test."""
        reset_gemini_client()

    @pytest.fixture(autouse=True)
    def auto_mock_gemini_environment(self, mock_gemini_settings, mock_llm_service):
        """Automatically mock Gemini environment for all tests."""
        # This fixture applies to all tests in the class
        pass

    @pytest.fixture
    def mock_gemini_settings(self):
        """Mock settings to use Gemini provider."""
        with patch("app.services.gemini_service.settings") as mock_settings:
            mock_settings.llm_provider = "gemini"
            mock_settings.google_api_key = "test-api-key"
            mock_settings.llm_model = "gemini-2.5-pro"
            mock_settings.llm_temperature = 0.1
            mock_settings.llm_max_tokens = 8192
            yield mock_settings

    @pytest.fixture
    def mock_genai_module(self):
        """Mock the google.generativeai module."""
        with patch("app.services.gemini_service.genai") as mock_genai:
            # Mock the configure method
            mock_genai.configure = MagicMock()

            # Mock the GenerativeModel
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            yield mock_genai, mock_model

    @pytest.fixture
    def mock_llm_service(self):
        """Mock the LLM service."""
        with patch("app.services.gemini_service.get_llm_service") as mock_service:
            mock_instance = MagicMock()
            # Make the generate_content method async
            mock_instance.generate_content = AsyncMock(
                return_value={
                    "response": json.dumps(
                        {
                            "project_title": "Test Project",
                            "estimated_value": {"amount": 1000000, "currency": "EUR"},
                        }
                    ),
                    "usage": {"total_token_count": 1500}
                }
            )
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_instance.get_provider_name.return_value = "gemini"
            mock_instance.get_provider_info.return_value = {
                "provider": "gemini", 
                "model": "gemini-2.5-pro"
            }
            mock_service.return_value = mock_instance
            yield mock_instance

    def test_client_initialization(self, mock_gemini_settings, mock_genai_module, mock_llm_service):
        """Test Gemini client initialization."""
        mock_genai, mock_model = mock_genai_module

        client = GeminiClient()

        # Verify configuration was called for Gemini
        mock_genai.configure.assert_called_once_with(api_key="test-api-key")

        # Verify model was created
        mock_genai.GenerativeModel.assert_called_once()

        assert client._model is not None
        assert client._llm_service is not None

    @pytest.mark.asyncio
    async def test_successful_content_generation(
        self, mock_gemini_settings, mock_genai_module, mock_llm_service
    ):
        """Test successful content generation."""
        mock_genai, mock_model = mock_genai_module

        # Mock successful response
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "project_title": "Test Project",
                "estimated_value": {"amount": 1000000, "currency": "EUR"},
            }
        )
        mock_response.usage_metadata.total_token_count = 1500

        mock_model.generate_content.return_value = mock_response

        client = GeminiClient()

        result = await client.generate_content("Test prompt")

        # Verify the response was parsed correctly
        assert "project_title" in result
        assert result["project_title"] == "Test Project"
        assert "_metadata" in result
        assert result["_metadata"]["actual_tokens"] == 1500

    @pytest.mark.asyncio
    async def test_json_parsing_from_markdown(self, mock_genai_module):
        """Test JSON parsing from markdown code blocks."""
        mock_genai, mock_model = mock_genai_module

        # Mock response with JSON in markdown
        mock_response = MagicMock()
        mock_response.text = """
        Here's the extracted data:
        
        ```json
        {
            "project_title": "Highway Project",
            "estimated_value": {"amount": 5000000, "currency": "EUR"}
        }
        ```
        """
        mock_response.usage_metadata.total_token_count = 1200

        mock_model.generate_content.return_value = mock_response

        client = GeminiClient()

        result = await client.generate_content("Test prompt")

        # Verify JSON was extracted from markdown
        assert "project_title" in result
        assert result["project_title"] == "Highway Project"

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, mock_genai_module):
        """Test rate limit error handling and retries."""
        mock_genai, mock_model = mock_genai_module

        from google.api_core.exceptions import ResourceExhausted

        # Mock rate limit error on first call, success on second
        mock_model.generate_content.side_effect = [
            ResourceExhausted("Rate limit exceeded"),
            MagicMock(text='{"success": true}', usage_metadata=MagicMock(total_token_count=100)),
        ]

        client = GeminiClient()

        # Should succeed after retry
        result = await client.generate_content("Test prompt")
        assert "success" in result

        # Verify it was called twice (original + retry)
        assert mock_model.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_quota_exceeded_error(self, mock_genai_module):
        """Test quota exceeded error handling."""
        mock_genai, mock_model = mock_genai_module

        from google.api_core.exceptions import ResourceExhausted

        # Mock quota exceeded error
        mock_model.generate_content.side_effect = ResourceExhausted("quota exceeded")

        client = GeminiClient()

        with pytest.raises(GeminiQuotaExceededError):
            await client.generate_content("Test prompt")

    @pytest.mark.asyncio
    async def test_invalid_argument_error(self, mock_genai_module):
        """Test invalid argument error handling."""
        mock_genai, mock_model = mock_genai_module

        from google.api_core.exceptions import InvalidArgument

        # Mock invalid argument error
        mock_model.generate_content.side_effect = InvalidArgument("Invalid input")

        client = GeminiClient()

        with pytest.raises(GeminiModelError) as exc_info:
            await client.generate_content("Test prompt")

        assert "Invalid input" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_genai_module):
        """Test timeout handling."""
        mock_genai, mock_model = mock_genai_module

        import asyncio

        # Mock timeout
        async def timeout_side_effect(*args, **kwargs):
            await asyncio.sleep(10)  # This will timeout

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            client = GeminiClient()

            with pytest.raises(GeminiAPIException) as exc_info:
                await client.generate_content("Test prompt", timeout=1.0)

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_retry_logic(self, mock_genai_module):
        """Test retry logic with exponential backoff."""
        mock_genai, mock_model = mock_genai_module

        from google.api_core.exceptions import GoogleAPICallError

        # Mock API error that should be retried
        mock_model.generate_content.side_effect = [
            GoogleAPICallError("Temporary error"),
            GoogleAPICallError("Another error"),
            MagicMock(text='{"success": true}', usage_metadata=MagicMock(total_token_count=100)),
        ]

        client = GeminiClient()

        # Should succeed after retries
        result = await client.generate_content("Test prompt", retry_attempts=3)
        assert "success" in result

        # Verify all three attempts were made
        assert mock_model.generate_content.call_count == 3

    @pytest.mark.asyncio
    async def test_token_estimation(self):
        """Test token estimation logic."""
        client = GeminiClient()

        # Test string estimation
        short_text = "Hello"
        long_text = "A" * 1000

        short_estimate = client._estimate_tokens(short_text)
        long_estimate = client._estimate_tokens(long_text)

        assert short_estimate < long_estimate
        assert short_estimate >= 100  # Minimum estimate

        # Test multimodal content estimation
        multimodal_content = [
            "Some text content",
            {"mime_type": "image/png", "data": b"fake_image_data"},
        ]

        multimodal_estimate = client._estimate_tokens(multimodal_content)
        assert multimodal_estimate > client._estimate_tokens("Some text content")

    @pytest.mark.asyncio
    async def test_connection_test(self, mock_gemini_settings, mock_genai_module, mock_llm_service):
        """Test API connection testing."""
        mock_genai, mock_model = mock_genai_module

        client = GeminiClient()

        result = await client.test_connection()

        assert result["status"] == "success"
        assert "message" in result
        assert result["message"] == "gemini connection successful"

    @pytest.mark.asyncio
    async def test_usage_stats(self):
        """Test usage statistics retrieval."""
        with patch("app.services.gemini_service.get_rate_limiter") as mock_get_limiter:
            mock_limiter = MagicMock()
            mock_limiter.get_current_limits.return_value = {
                "available_requests": 100,
                "available_tokens": 50000,
            }
            mock_limiter.get_stats.return_value = {"total_requests": 50, "total_tokens": 25000}
            mock_get_limiter.return_value = mock_limiter

            client = GeminiClient()
            stats = client.get_usage_stats()

            assert "rate_limits" in stats
            assert "stats" in stats
            assert "model" in stats

    @pytest.mark.asyncio
    async def test_multimodal_content_handling(self, mock_genai_module):
        """Test handling of multimodal content (text + images)."""
        mock_genai, mock_model = mock_genai_module

        # Mock successful response
        mock_response = MagicMock()
        mock_response.text = '{"image_analysis": "Highway construction site"}'
        mock_response.usage_metadata.total_token_count = 2000

        mock_model.generate_content.return_value = mock_response

        client = GeminiClient()

        # Test with multimodal content
        multimodal_prompt = [
            "Analyze this image",
            {"mime_type": "image/jpeg", "data": b"fake_image_data"},
        ]

        result = await client.generate_content(multimodal_prompt)

        assert "image_analysis" in result
        assert result["_metadata"]["actual_tokens"] == 2000

    def test_singleton_pattern(self):
        """Test that get_gemini_client returns the same instance."""
        client1 = get_gemini_client()
        client2 = get_gemini_client()

        assert client1 is client2

        # Test reset functionality
        reset_gemini_client()
        client3 = get_gemini_client()

        assert client3 is not client1
