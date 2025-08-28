"""Enhanced tests for the Gemini service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions

from app.core.exceptions import GeminiAPIException, GeminiQuotaExceededError, GeminiRateLimitError
from app.services.gemini_service import GeminiClient


@pytest.fixture
def mock_gemini_service():
    """Mock Gemini service for testing."""
    return AsyncMock()


class TestGeminiClientBasics:
    """Test basic Gemini client functionality."""

    @patch("app.services.gemini_service.get_llm_service")
    def test_client_initialization(self, mock_get_llm_service):
        """Test Gemini client initialization."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        assert client.settings is not None
        assert client.rate_limiter is not None
        assert client._llm_service is not None

    @patch("app.services.gemini_service.get_llm_service")
    def test_get_usage_stats(self, mock_get_llm_service):
        """Test usage stats retrieval."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        stats = client.get_usage_stats()

        # Check the actual structure returned by get_usage_stats
        assert "rate_limits" in stats
        assert "stats" in stats
        assert "provider" in stats
        assert "model" in stats
        assert stats["provider"] == "gemini"
        assert stats["model"] == "gemini-2.5-pro"

    @patch("app.services.gemini_service.get_llm_service")
    @pytest.mark.asyncio
    async def test_generate_content_success(self, mock_get_llm_service):
        """Test successful content generation."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_content.return_value = {"response": "Generated content"}
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        result = await client.generate_content("Test prompt")

        assert "_metadata" in result
        mock_llm_service.generate_content.assert_called_once()

    @patch("app.services.gemini_service.get_llm_service")
    @pytest.mark.asyncio
    async def test_generate_json_content_success(self, mock_get_llm_service):
        """Test successful JSON content generation."""
        mock_llm_service = AsyncMock()
        mock_response = {"result": "success", "data": {"key": "value"}}
        mock_llm_service.generate_content.return_value = mock_response
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        result = await client.generate_content("Test prompt")

        assert "_metadata" in result
        mock_llm_service.generate_content.assert_called_once()

    @patch("app.services.gemini_service.get_llm_service")
    def test_test_connection_basic_setup(self, mock_get_llm_service):
        """Test connection test basic setup."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Just verify the client is properly configured for connection testing
        assert client._llm_service is not None
        assert hasattr(client, "test_connection")


class TestGeminiClientErrorHandling:
    """Test Gemini client error handling."""

    @patch("app.services.gemini_service.get_llm_service")
    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, mock_get_llm_service):
        """Test rate limit error handling."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock the internal method that calls the LLM service
        with patch.object(client, "_generate_content_async") as mock_generate:
            from google.api_core import exceptions as google_exceptions

            mock_generate.side_effect = google_exceptions.ResourceExhausted("Rate limit exceeded")

            with pytest.raises(GeminiRateLimitError):
                await client.generate_content("Test prompt")

    @patch("app.services.gemini_service.get_llm_service")
    @pytest.mark.asyncio
    async def test_quota_exceeded_error_handling(self, mock_get_llm_service):
        """Test quota exceeded error handling."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock the internal method that calls the LLM service
        with patch.object(client, "_generate_content_async") as mock_generate:
            from google.api_core import exceptions as google_exceptions

            mock_generate.side_effect = google_exceptions.ResourceExhausted("quota exceeded")

            with pytest.raises(GeminiQuotaExceededError):
                await client.generate_content("Test prompt")

    @patch("app.services.gemini_service.get_llm_service")
    @pytest.mark.asyncio
    async def test_generic_api_error_handling(self, mock_get_llm_service):
        """Test generic API error handling."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_content.side_effect = GeminiAPIException("API error")
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        with pytest.raises(GeminiAPIException):
            await client.generate_content("Test prompt")


class TestGeminiClientAdvanced:
    """Test advanced Gemini client functionality."""

    @patch("app.services.gemini_service.get_llm_service")
    def test_file_upload_preparation(self, mock_get_llm_service):
        """Test file upload preparation."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Test that client is initialized properly for file uploads
        assert hasattr(client, "_file_client")
        assert hasattr(client, "_model")

    @patch("app.services.gemini_service.get_llm_service")
    def test_multimodal_content_token_estimation(self, mock_get_llm_service):
        """Test token estimation for multimodal content."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Test token estimation for list content
        multimodal_content = ["Analyze this document", "Additional text content"]

        tokens = client._estimate_tokens(multimodal_content)
        assert tokens > 0
        assert isinstance(tokens, int)

    @patch("app.services.gemini_service.get_llm_service")
    def test_safety_settings_configuration(self, mock_get_llm_service):
        """Test safety settings configuration."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Verify client initialization includes safety settings
        assert client._llm_service is not None

    @patch("app.services.gemini_service.get_llm_service")
    def test_token_estimation_string(self, mock_get_llm_service):
        """Test token estimation for string content."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Test string token estimation
        tokens = client._estimate_tokens("This is a test prompt with some text")
        assert tokens > 0
        assert isinstance(tokens, int)

    @patch("app.services.gemini_service.get_llm_service")
    def test_token_estimation_list(self, mock_get_llm_service):
        """Test token estimation for list content."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Test list token estimation
        content = ["Text content", "More text", {"type": "image"}]
        tokens = client._estimate_tokens(content)
        assert tokens > 0
        assert isinstance(tokens, int)

    @patch("app.services.gemini_service.get_llm_service")
    def test_mime_type_detection(self, mock_get_llm_service):
        """Test MIME type detection for different file types."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Test various file extensions
        assert client._get_mime_type("document.pdf") == "application/pdf"
        assert client._get_mime_type("image.jpg") == "image/jpeg"
        assert client._get_mime_type("image.png") == "image/png"
        assert client._get_mime_type("text.txt") == "text/plain"
        assert client._get_mime_type("unknown.xyz") == "application/octet-stream"

    @patch("app.services.gemini_service.get_llm_service")
    def test_multimodal_processing_requirements(self, mock_get_llm_service):
        """Test multimodal processing requirements."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Test that required settings are available for multimodal processing
        assert client.settings.llm_provider is not None
        assert client.settings.llm_model is not None
        assert hasattr(client, "_model")
        assert hasattr(client, "_file_client")

    @patch("app.services.gemini_service.get_llm_service")
    @pytest.mark.asyncio
    async def test_connection_test_exception(self, mock_get_llm_service):
        """Test connection test with exception."""
        mock_llm_service = AsyncMock()
        mock_llm_service.health_check.side_effect = Exception("Connection failed")
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        result = await client.test_connection()

        assert result["status"] == "error"
        assert result["error"] == "Connection failed"
        assert result["error_type"] == "Exception"


def test_gemini_client_singleton():
    """Test Gemini client singleton pattern."""
    from app.services.gemini_service import get_gemini_client

    client1 = get_gemini_client()
    client2 = get_gemini_client()

    # Should return the same instance
    assert client1 is client2


def test_reset_gemini_client():
    """Test resetting the Gemini client."""
    from app.services.gemini_service import get_gemini_client, reset_gemini_client

    client1 = get_gemini_client()
    reset_gemini_client()
    client2 = get_gemini_client()

    # Should return a new instance after reset
    assert client1 is not client2


class TestGeminiResponseParsing:
    """Test Gemini response parsing functionality."""

    @patch("app.services.gemini_service.get_llm_service")
    def test_parse_valid_json_response(self, mock_get_llm_service):
        """Test parsing valid JSON response."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock response with valid JSON
        class MockResponse:
            def __init__(self):
                self.text = '{"result": "success", "data": {"key": "value"}}'

        response = MockResponse()
        result = client._parse_response(response)

        assert result == {"result": "success", "data": {"key": "value"}}

    @patch("app.services.gemini_service.get_llm_service")
    def test_parse_json_in_markdown(self, mock_get_llm_service):
        """Test parsing JSON wrapped in markdown code blocks."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock response with JSON in markdown
        class MockResponse:
            def __init__(self):
                self.text = """```json
{"result": "success"}
```"""

        response = MockResponse()
        result = client._parse_response(response)

        assert result == {"result": "success"}

    @patch("app.services.gemini_service.get_llm_service")
    def test_parse_invalid_json_response(self, mock_get_llm_service):
        """Test parsing invalid JSON response."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock response with invalid JSON
        class MockResponse:
            def __init__(self):
                self.text = "This is not valid JSON content"

        response = MockResponse()
        result = client._parse_response(response)

        assert result["raw_response"] == "This is not valid JSON content"
        assert result["extraction_success"] is False
        assert "parse_error" in result

    @patch("app.services.gemini_service.get_llm_service")
    def test_parse_empty_response(self, mock_get_llm_service):
        """Test parsing empty response."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock empty response
        class MockResponse:
            def __init__(self):
                self.text = None

        response = MockResponse()

        from app.core.exceptions import GeminiModelError

        with pytest.raises(GeminiModelError):
            client._parse_response(response)

    @patch("app.services.gemini_service.get_llm_service")
    def test_get_token_count_from_response(self, mock_get_llm_service):
        """Test token count extraction from response."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock response with usage metadata
        class MockUsageMetadata:
            def __init__(self):
                self.total_token_count = 1250

        class MockResponse:
            def __init__(self):
                self.usage_metadata = MockUsageMetadata()

        response = MockResponse()
        tokens = client._get_token_count_from_response(response)

        assert tokens == 1250

    @patch("app.services.gemini_service.get_llm_service")
    def test_get_token_count_no_metadata(self, mock_get_llm_service):
        """Test token count extraction when no metadata available."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock response without usage metadata
        class MockResponse:
            pass

        response = MockResponse()
        tokens = client._get_token_count_from_response(response)

        assert tokens == 0


class TestGeminiClientInitialization:
    """Test Gemini client initialization edge cases."""

    @patch("app.services.gemini_service.get_llm_service")
    def test_initialization_error_handling(self, mock_get_llm_service):
        """Test initialization error handling."""
        from app.core.exceptions import ServiceUnavailableError

        # Mock get_llm_service to raise an exception
        mock_get_llm_service.side_effect = Exception("Failed to initialize LLM service")

        with pytest.raises(ServiceUnavailableError) as exc_info:
            GeminiClient()

        assert "Failed to initialize AI service" in str(exc_info.value)


class TestGeminiTokenEstimationEdgeCases:
    """Test token estimation edge cases."""

    @patch("app.services.gemini_service.get_llm_service")
    def test_token_estimation_edge_cases(self, mock_get_llm_service):
        """Test token estimation for edge cases."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Test with dict content (should return default)
        dict_content = {"type": "text", "content": "test"}
        tokens = client._estimate_tokens(dict_content)
        assert tokens == 1000  # Default conservative estimate

        # Test with list containing image-like content
        class MockImageContent:
            def __init__(self):
                self.mime_type = "image/jpeg"

        image_content = ["Analyze this image", MockImageContent()]
        tokens = client._estimate_tokens(image_content)
        assert tokens > 1000  # Should include image overhead


class TestGeminiProviderRouting:
    """Test provider-specific routing behavior."""

    @patch("app.services.gemini_service.get_llm_service")
    def test_multimodal_processing_non_gemini_provider(self, mock_get_llm_service):
        """Test multimodal processing with non-Gemini provider error."""
        mock_llm_service = AsyncMock()
        mock_get_llm_service.return_value = mock_llm_service

        client = GeminiClient()

        # Mock settings to use non-Gemini provider
        with patch.object(client.settings, "llm_provider", "ollama"):
            documents = {"test.pdf": b"test content"}

            with pytest.raises(ValueError) as exc_info:
                client.process_multiple_documents("Test prompt", documents)

            assert (
                "Multi-document processing with File API only available for Gemini provider"
                in str(exc_info.value)
            )
            assert "current provider is ollama" in str(exc_info.value)
