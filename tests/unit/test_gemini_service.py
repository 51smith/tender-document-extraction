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
    async def test_json_parsing_from_markdown(self, mock_gemini_settings, mock_genai_module, mock_llm_service):
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

        # Use a list to trigger Gemini model path instead of LLM service path
        result = await client.generate_content(["Test prompt"])

        # Verify JSON was extracted from markdown
        assert "project_title" in result
        assert result["project_title"] == "Highway Project"

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, mock_gemini_settings, mock_genai_module, mock_llm_service):
        """Test rate limit error handling and retries."""
        mock_genai, mock_model = mock_genai_module

        from google.api_core.exceptions import ResourceExhausted

        # Mock rate limit error on first call, success on second
        mock_model.generate_content.side_effect = [
            ResourceExhausted("Rate limit exceeded"),
            MagicMock(text='{"success": true}', usage_metadata=MagicMock(total_token_count=100)),
        ]

        client = GeminiClient()

        # Should succeed after retry - use list to trigger Gemini path
        result = await client.generate_content(["Test prompt"])
        assert "success" in result

        # Verify it was called twice (original + retry)
        assert mock_model.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_quota_exceeded_error(self, mock_gemini_settings, mock_genai_module, mock_llm_service):
        """Test quota exceeded error handling."""
        mock_genai, mock_model = mock_genai_module

        from google.api_core.exceptions import ResourceExhausted

        # Mock quota exceeded error
        mock_model.generate_content.side_effect = ResourceExhausted("quota exceeded")

        client = GeminiClient()

        with pytest.raises(GeminiQuotaExceededError):
            await client.generate_content(["Test prompt"])

    @pytest.mark.asyncio
    async def test_invalid_argument_error(self, mock_gemini_settings, mock_genai_module, mock_llm_service):
        """Test invalid argument error handling."""
        mock_genai, mock_model = mock_genai_module

        from google.api_core.exceptions import InvalidArgument

        # Mock invalid argument error
        mock_model.generate_content.side_effect = InvalidArgument("Invalid input")

        client = GeminiClient()

        with pytest.raises(GeminiModelError) as exc_info:
            await client.generate_content(["Test prompt"])

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
    async def test_retry_logic(self, mock_gemini_settings, mock_genai_module, mock_llm_service):
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

        # Should succeed after retries - use list to trigger Gemini path
        result = await client.generate_content(["Test prompt"], retry_attempts=3)
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


class TestGeminiServiceCoverageMissingLines:
    """Tests to improve Gemini service coverage targeting 223 missing lines."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup method to reset client before each test."""
        reset_gemini_client()

    @pytest.fixture
    def mock_non_gemini_settings(self):
        """Mock settings for non-Gemini provider."""
        with patch("app.services.gemini_service.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_settings.llm_model = "llama3.3:latest"
            mock_settings.llm_temperature = 0.1
            mock_settings.llm_max_tokens = 4096
            yield mock_settings

    @pytest.fixture
    def mock_llm_service(self):
        """Mock the LLM service."""
        with patch("app.services.gemini_service.get_llm_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.generate_content = AsyncMock(return_value={
                "response": json.dumps({"project_title": "Test"}),
                "usage": {"total_token_count": 500}
            })
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_instance.get_provider_name.return_value = "ollama"
            mock_instance.get_provider_info.return_value = {"provider": "ollama", "model": "llama3.3"}
            mock_service.return_value = mock_instance
            yield mock_instance

    def test_init_non_gemini_provider(self, mock_non_gemini_settings, mock_llm_service):
        """Test initialization with non-Gemini provider (lines 31-43, 46, 86-88)."""
        with patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter:
            mock_rate_limiter.return_value = MagicMock()

            client = GeminiClient()

            # Verify basic initialization (lines 31-37)
            assert client.settings == mock_non_gemini_settings
            assert client._client is None
            assert client._file_client is None
            assert client._model is None
            assert client._llm_service is not None

    def test_init_gemini_provider_full_setup(self):
        """Test full Gemini provider initialization (lines 46-84)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service") as mock_llm_service, \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter, \
             patch("app.services.gemini_service.genai") as mock_genai, \
             patch("app.services.gemini_service.genai_client") as mock_genai_client:
            
            # Setup Gemini provider settings
            mock_settings.llm_provider = "gemini"
            mock_settings.google_api_key = "test-key"
            mock_settings.llm_model = "gemini-2.5-pro"
            mock_settings.llm_temperature = 0.1
            mock_settings.llm_max_tokens = 8192

            mock_llm_service_instance = MagicMock()
            mock_llm_service.return_value = mock_llm_service_instance
            mock_rate_limiter.return_value = MagicMock()

            # Mock GenerativeModel and Client
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model
            mock_file_client = MagicMock()
            mock_genai_client.Client.return_value = mock_file_client

            client = GeminiClient()

            # Verify Gemini-specific initialization (lines 47-84)
            mock_genai.configure.assert_called_once_with(api_key="test-key")
            mock_genai.GenerativeModel.assert_called_once()
            mock_genai_client.Client.assert_called_once_with(api_key="test-key")

            assert client._model == mock_model
            assert client._file_client == mock_file_client

    def test_init_exception_handling(self):
        """Test initialization exception handling (lines 90-92)."""
        with patch("app.services.gemini_service.get_llm_service") as mock_llm_service, \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter:
            
            # Make LLM service initialization fail
            mock_llm_service.side_effect = Exception("LLM service failed")
            mock_rate_limiter.return_value = MagicMock()

            from app.core.exceptions import ServiceUnavailableError
            with pytest.raises(ServiceUnavailableError) as exc_info:
                GeminiClient()

            assert "Failed to initialize AI service" in str(exc_info.value)

    def test_estimate_tokens_string(self):
        """Test token estimation for string content (lines 96-98)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            client = GeminiClient()
            
            # Test short string (should return minimum 100)
            short_estimate = client._estimate_tokens("hi")
            assert short_estimate == 100
            
            # Test longer string
            long_string = "A" * 1000
            long_estimate = client._estimate_tokens(long_string)
            assert long_estimate == 250  # 1000 // 4

    def test_estimate_tokens_multimodal(self):
        """Test token estimation for multimodal content (lines 99-109)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            client = GeminiClient()
            
            # Test multimodal content with image
            image_obj = MagicMock()
            image_obj.mime_type = "image/jpeg"
            
            multimodal_content = [
                "Some text content",  # 4 tokens
                image_obj,  # 1000 tokens
                "More text"  # 2 tokens
            ]
            
            estimate = client._estimate_tokens(multimodal_content)
            assert estimate == 1006  # 4 + 1000 + 2

    def test_estimate_tokens_default(self):
        """Test token estimation default case (lines 110-111)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            client = GeminiClient()
            
            # Test with non-string, non-list input
            estimate = client._estimate_tokens(42)
            assert estimate == 1000  # Default conservative estimate

    @pytest.mark.asyncio
    async def test_generate_content_timeout_error(self):
        """Test timeout error handling (lines 158-160)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter:
            
            mock_rate_limiter.return_value.wait_for_capacity = AsyncMock()
            
            client = GeminiClient()
            
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                with pytest.raises(GeminiAPIException) as exc_info:
                    await client.generate_content("test", timeout=1.0, retry_attempts=1)
                
                assert "timed out after 1.0s" in str(exc_info.value)

    @pytest.mark.asyncio 
    async def test_generate_content_rate_limit_retry(self):
        """Test rate limit error with exponential backoff (lines 166-170)."""
        from google.api_core.exceptions import ResourceExhausted
        
        with patch("app.services.gemini_service.get_llm_service") as mock_llm, \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            
            mock_rate_limiter.return_value.wait_for_capacity = AsyncMock()
            mock_rate_limiter.return_value.record_token_usage = MagicMock()
            
            client = GeminiClient()
            
            # Mock _generate_content_async to raise rate limit error then succeed
            responses = [
                ResourceExhausted("Rate limit exceeded"),
                MagicMock(text='{"success": true}', usage_metadata=MagicMock(total_token_count=100))
            ]
            
            with patch.object(client, '_generate_content_async', side_effect=responses):
                result = await client.generate_content("test", retry_attempts=2)
                
                # Verify exponential backoff was applied (line 168)
                mock_sleep.assert_called_with(2.0)  # 2^1 * 1.0
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_content_api_error_retry(self):
        """Test Google API error with exponential backoff (lines 176-182)."""
        from google.api_core.exceptions import GoogleAPICallError
        
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            
            mock_rate_limiter.return_value.wait_for_capacity = AsyncMock()
            mock_rate_limiter.return_value.record_token_usage = MagicMock()
            
            client = GeminiClient()
            
            # Mock API error then success
            responses = [
                GoogleAPICallError("Temporary API error"),
                MagicMock(text='{"success": true}', usage_metadata=MagicMock(total_token_count=100))
            ]
            
            with patch.object(client, '_generate_content_async', side_effect=responses):
                result = await client.generate_content("test", retry_attempts=2)
                
                # Verify exponential backoff with 0.5 multiplier (line 181)
                mock_sleep.assert_called_with(1.0)  # 2^1 * 0.5
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_content_unexpected_error(self):
        """Test unexpected error handling (lines 184-189)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            
            mock_rate_limiter.return_value.wait_for_capacity = AsyncMock()
            
            client = GeminiClient()
            
            # Mock unexpected error then success
            responses = [
                ValueError("Unexpected error"),
                MagicMock(text='{"success": true}', usage_metadata=MagicMock(total_token_count=100))
            ]
            
            with patch.object(client, '_generate_content_async', side_effect=responses):
                result = await client.generate_content("test", retry_attempts=2)
                
                # Verify 1.0 second wait for unexpected errors (line 189)
                mock_sleep.assert_called_with(1.0)
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_generate_content_all_retries_fail(self):
        """Test when all retry attempts fail (lines 192-193)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter:
            
            mock_rate_limiter.return_value.wait_for_capacity = AsyncMock()
            
            client = GeminiClient()
            
            # Mock all attempts to fail
            with patch.object(client, '_generate_content_async', side_effect=Exception("Persistent error")):
                with pytest.raises(GeminiAPIException) as exc_info:
                    await client.generate_content("test", retry_attempts=2)
                
                assert "Unexpected error: Persistent error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_content_async_multimodal_gemini(self):
        """Test multimodal content with Gemini provider (lines 199-206)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"), \
             patch("asyncio.get_event_loop") as mock_get_loop:
            
            mock_settings.llm_provider = "gemini"
            
            client = GeminiClient()
            client._model = MagicMock()
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_response = MagicMock()
            mock_loop.run_in_executor.return_value = asyncio.Future()
            mock_loop.run_in_executor.return_value.set_result(mock_response)
            
            result = await client._generate_content_async(["text", "image"])
            
            # Verify multimodal path was taken (line 206)
            mock_loop.run_in_executor.assert_called_once()
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_generate_content_async_text_conversion(self):
        """Test multimodal to text conversion for non-Gemini (lines 209-217)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service") as mock_llm_service, \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            mock_settings.llm_provider = "ollama"
            
            mock_llm_instance = MagicMock()
            mock_llm_instance.generate_content = AsyncMock(return_value={"response": "text response"})
            mock_llm_service.return_value = mock_llm_instance
            
            client = GeminiClient()
            
            # Test with mixed multimodal content (lines 210-217)
            text_obj = MagicMock()
            text_obj.text = "extracted text"
            
            multimodal_prompt = [
                "regular text",
                text_obj,
                "more text"
            ]
            
            await client._generate_content_async(multimodal_prompt)
            
            # Verify text conversion logic was executed
            mock_llm_instance.generate_content.assert_called_once()
            call_args = mock_llm_instance.generate_content.call_args
            assert "regular text" in call_args[0][0]
            assert "extracted text" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_generate_content_async_compatible_response(self):
        """Test CompatibleResponse class functionality (lines 225-244)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service") as mock_llm_service, \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            mock_settings.llm_provider = "ollama"
            
            mock_llm_instance = MagicMock()
            mock_llm_service.return_value = mock_llm_instance
            
            client = GeminiClient()
            
            # Test dict with "response" key (lines 227-229)
            mock_llm_instance.generate_content = AsyncMock(return_value={
                "response": "test response",
                "usage": {"total_token_count": 150}
            })
            
            result = await client._generate_content_async("test")
            
            assert result.text == "test response"
            assert result.usage_metadata.total_token_count == 150

    def test_get_token_count_from_response(self):
        """Test token count extraction (lines 249-256)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            client = GeminiClient()
            
            # Test response with usage_metadata (lines 252-253)
            response_with_metadata = MagicMock()
            response_with_metadata.usage_metadata.total_token_count = 500
            assert client._get_token_count_from_response(response_with_metadata) == 500
            
            # Test response without usage_metadata (line 254)
            response_without_metadata = MagicMock()
            del response_without_metadata.usage_metadata
            assert client._get_token_count_from_response(response_without_metadata) == 0
            
            # Test exception case (line 256)
            with patch.object(client, '_get_token_count_from_response', side_effect=Exception):
                assert client._get_token_count_from_response(None) == 0

    def test_parse_response_empty_response(self):
        """Test parsing empty response (lines 270-272)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            mock_settings.llm_model = "test-model"
            
            client = GeminiClient()
            
            # Test empty response (line 270)
            empty_response = MagicMock()
            empty_response.text = None
            
            from app.core.exceptions import GeminiModelError
            with pytest.raises(GeminiModelError) as exc_info:
                client._parse_response(empty_response)
                
            assert "Empty response from Gemini API" in str(exc_info.value)

    def test_parse_response_json_decode_error(self):
        """Test JSON decode error handling (lines 279-301)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            client = GeminiClient()
            
            # Test invalid JSON (lines 279-282)
            response = MagicMock()
            response.text = "invalid json content"
            
            result = client._parse_response(response)
            
            # Should return raw response when JSON parsing fails (lines 304-308)
            assert result["raw_response"] == "invalid json content"
            assert "parse_error" in result
            assert result["extraction_success"] is False

    def test_parse_response_markdown_json_extraction(self):
        """Test JSON extraction from markdown (lines 289-301)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            client = GeminiClient()
            
            # Test markdown with valid JSON (lines 289-298)
            response = MagicMock()
            response.text = """
            Some text before
            ```json
            {"project_title": "Extracted Project", "value": 1000}
            ```
            Some text after
            """
            
            result = client._parse_response(response)
            
            assert result["project_title"] == "Extracted Project"
            assert result["value"] == 1000

    def test_parse_response_markdown_json_decode_error(self):
        """Test markdown JSON decode error (lines 299-301)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            client = GeminiClient()
            
            # Test markdown with invalid JSON (lines 289-301)
            response = MagicMock()
            response.text = """
            ```json
            {invalid json content
            ```
            """
            
            result = client._parse_response(response)
            
            # Should return raw response when markdown JSON parsing fails
            assert result["raw_response"] == response.text.strip()
            assert result["extraction_success"] is False

    def test_parse_response_general_exception(self):
        """Test general exception in response parsing (lines 310-311)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            mock_settings.llm_model = "test-model"
            
            client = GeminiClient()
            
            # Force an exception during parsing
            response = MagicMock()
            response.text = '{"valid": "json"}'
            
            with patch("json.loads", side_effect=Exception("Parsing error")):
                from app.core.exceptions import GeminiModelError
                with pytest.raises(GeminiModelError) as exc_info:
                    client._parse_response(response)
                
                assert "Failed to parse response: Parsing error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_test_connection_health_check_failure(self):
        """Test connection test when health check fails (lines 325-332)."""
        with patch("app.services.gemini_service.get_llm_service") as mock_llm_service, \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            mock_llm_instance = MagicMock()
            mock_llm_instance.health_check = AsyncMock(return_value=False)
            mock_llm_instance.get_provider_info.return_value = {"provider": "test"}
            mock_llm_service.return_value = mock_llm_instance
            
            client = GeminiClient()
            
            result = await client.test_connection()
            
            assert result["status"] == "error"
            assert result["error"] == "Health check failed"
            assert result["provider"] == "test"

    @pytest.mark.asyncio
    async def test_test_connection_exception(self):
        """Test connection test exception handling (lines 334-335)."""
        with patch("app.services.gemini_service.get_llm_service") as mock_llm_service, \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            mock_llm_instance = MagicMock()
            mock_llm_instance.health_check = AsyncMock(side_effect=Exception("Connection failed"))
            mock_llm_service.return_value = mock_llm_instance
            
            client = GeminiClient()
            
            result = await client.test_connection()
            
            assert result["status"] == "error"
            assert result["error"] == "Connection failed"
            assert result["error_type"] == "Exception"

    @pytest.mark.asyncio
    async def test_process_multiple_documents_non_gemini_error(self):
        """Test multi-document processing with non-Gemini provider (lines 347-350)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            mock_settings.llm_provider = "ollama"  # Non-Gemini provider
            
            client = GeminiClient()
            
            documents = {"doc1.pdf": b"content1"}
            prompt = "Extract data"
            
            with pytest.raises(ValueError) as exc_info:
                await client.process_multiple_documents(documents, prompt)
            
            assert "Multi-document processing with File API only available for Gemini provider" in str(exc_info.value)
            assert "current provider is ollama" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_multiple_documents_gemini_success(self):
        """Test successful multi-document processing with Gemini (lines 352-421)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter, \
             patch("app.services.gemini_service.genai_client") as mock_genai_client:
            
            mock_settings.llm_provider = "gemini"
            mock_settings.llm_model = "gemini-2.5-pro"
            
            # Setup rate limiter
            mock_rate_limiter.return_value.wait_for_capacity = AsyncMock()
            mock_rate_limiter.return_value.record_token_usage = MagicMock()
            
            # Setup file client
            mock_file_client = MagicMock()
            mock_genai_client.Client.return_value = mock_file_client
            
            # Mock uploaded files
            mock_uploaded_file1 = MagicMock()
            mock_uploaded_file1.name = "file1_id"
            mock_uploaded_file2 = MagicMock()
            mock_uploaded_file2.name = "file2_id"
            
            mock_file_client.files.upload.side_effect = [mock_uploaded_file1, mock_uploaded_file2]
            mock_file_client.files.delete = MagicMock()
            
            # Mock successful API response
            mock_response = MagicMock()
            mock_response.text = '{"project_title": "Multi-doc Project"}'
            mock_response.usage_metadata.total_token_count = 2000
            
            client = GeminiClient()
            client._file_client = mock_file_client
            
            # Mock the async content generation
            with patch.object(client, '_generate_multi_document_content_async', return_value=mock_response):
                documents = {
                    "doc1.pdf": b"content1",
                    "doc2.txt": b"content2"
                }
                
                result = await client.process_multiple_documents(documents, "Extract data")
                
                # Verify file uploads (lines 358-373)
                assert mock_file_client.files.upload.call_count == 2
                
                # Verify API call was made (lines 392-395)
                assert result["project_title"] == "Multi-doc Project"
                assert result["_metadata"]["num_documents"] == 2
                assert result["_metadata"]["uploaded_files"] == ["file1_id", "file2_id"]
                
                # Verify cleanup (lines 461-463)
                assert mock_file_client.files.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_process_multiple_documents_upload_error_cleanup(self):
        """Test cleanup when document upload fails (lines 458-465)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter, \
             patch("app.services.gemini_service.genai_client") as mock_genai_client:
            
            mock_settings.llm_provider = "gemini"
            
            mock_rate_limiter.return_value.wait_for_capacity = AsyncMock()
            
            # Setup file client
            mock_file_client = MagicMock()
            mock_genai_client.Client.return_value = mock_file_client
            
            # Mock successful first upload, then failure
            mock_uploaded_file = MagicMock()
            mock_uploaded_file.name = "file1_id"
            
            mock_file_client.files.upload.side_effect = [
                mock_uploaded_file,
                Exception("Upload failed")
            ]
            
            client = GeminiClient()
            client._file_client = mock_file_client
            
            documents = {"doc1.pdf": b"content1", "doc2.pdf": b"content2"}
            
            with pytest.raises(Exception):
                await client.process_multiple_documents(documents, "Extract")
            
            # Verify cleanup was attempted even on failure (lines 460-465)
            mock_file_client.files.delete.assert_called_once_with(name="file1_id")

    def test_get_mime_type(self):
        """Test MIME type determination (lines 467-484)."""
        with patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            client = GeminiClient()
            
            # Test known file types (lines 471-483)
            assert client._get_mime_type("document.pdf") == "application/pdf"
            assert client._get_mime_type("file.txt") == "text/plain"
            assert client._get_mime_type("image.jpg") == "image/jpeg"
            assert client._get_mime_type("image.png") == "image/png"
            assert client._get_mime_type("doc.docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            assert client._get_mime_type("page.html") == "text/html"
            
            # Test unknown file type (line 484)
            assert client._get_mime_type("unknown.xyz") == "application/octet-stream"
            
            # Test case insensitive (line 469)
            assert client._get_mime_type("IMAGE.JPEG") == "image/jpeg"

    @pytest.mark.asyncio
    async def test_generate_multi_document_content_async(self):
        """Test multi-document content generation (lines 486-498)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"), \
             patch("asyncio.get_event_loop") as mock_get_loop:
            
            mock_settings.llm_model = "gemini-2.5-pro"
            
            # Setup file client
            mock_file_client = MagicMock()
            mock_file_client.models.generate_content = MagicMock(return_value="mock_response")
            
            client = GeminiClient()
            client._file_client = mock_file_client
            
            # Setup async execution
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.run_in_executor.return_value = asyncio.Future()
            mock_loop.run_in_executor.return_value.set_result("mock_response")
            
            contents = ["file1", "file2", "prompt"]
            result = await client._generate_multi_document_content_async(contents)
            
            # Verify executor was called with correct lambda (lines 490-495)
            mock_loop.run_in_executor.assert_called_once()
            assert result == "mock_response"

    @pytest.mark.asyncio
    async def test_generate_multi_document_content_async_error(self):
        """Test multi-document content generation error (lines 496-498)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter"):
            
            mock_settings.llm_model = "gemini-2.5-pro"
            
            client = GeminiClient()
            client._file_client = None  # Force error
            
            with pytest.raises(Exception) as exc_info:
                await client._generate_multi_document_content_async(["content"])
            
            # Exception should be re-raised (line 498)
            assert exc_info.value is not None

    def test_get_usage_stats(self):
        """Test usage statistics retrieval (lines 500-507)."""
        with patch("app.services.gemini_service.settings") as mock_settings, \
             patch("app.services.gemini_service.get_llm_service"), \
             patch("app.services.gemini_service.get_rate_limiter") as mock_rate_limiter:
            
            mock_settings.llm_provider = "gemini"
            mock_settings.llm_model = "gemini-2.5-pro"
            
            # Setup rate limiter mocks
            mock_limiter = MagicMock()
            mock_limiter.get_current_limits.return_value = {"requests": 100, "tokens": 50000}
            mock_limiter.get_stats.return_value = {"total_requests": 50}
            mock_rate_limiter.return_value = mock_limiter
            
            client = GeminiClient()
            
            stats = client.get_usage_stats()
            
            # Verify all required fields are present (lines 502-507)
            assert "rate_limits" in stats
            assert stats["rate_limits"]["requests"] == 100
            assert "stats" in stats
            assert stats["stats"]["total_requests"] == 50
            assert stats["provider"] == "gemini"
            assert stats["model"] == "gemini-2.5-pro"
