"""Comprehensive tests for LLM service implementations."""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import openai
import pytest
from google import generativeai as genai

from app.core.exceptions import LLMError, LLMQuotaExceededError, LLMRateLimitError
from app.core.retry_config import get_retry_manager
from app.services.llm_service import (
    BaseLLMService,
    GeminiLLMService,
    LLMServiceFactory,
    OllamaLLMService,
    OpenAILLMService,
    get_llm_service,
)


@pytest.fixture(autouse=True)
def reset_circuit_breakers():
    """Reset circuit breakers before each test to ensure test isolation."""
    retry_manager = get_retry_manager()
    # Reset all circuit breakers
    for provider in ["gemini", "openai", "ollama"]:
        retry_manager.reset_circuit_breaker(provider)
    yield
    # Clean up after test
    for provider in ["gemini", "openai", "ollama"]:
        retry_manager.reset_circuit_breaker(provider)


class TestBaseLLMService:
    """Tests for the abstract base LLM service."""

    def test_base_service_initialization(self):
        """Test basic initialization of abstract base class."""

        # Cannot instantiate abstract class directly, but can test via subclass
        class ConcreteLLMService(BaseLLMService):
            async def _generate_content_impl(
                self, prompt, system_prompt=None, json_schema=None, **kwargs
            ):
                return {"response": "test"}

            async def health_check(self):
                return True

            def get_provider_name(self):
                return "test"

            def get_provider_info(self):
                return {"provider": "test"}

        service = ConcreteLLMService(model="test-model", temperature=0.2, max_tokens=4096)

        assert service.model == "test-model"
        assert service.temperature == 0.2
        assert service.max_tokens == 4096

    def test_base_service_default_values(self):
        """Test default initialization values."""

        class ConcreteLLMService(BaseLLMService):
            async def _generate_content_impl(
                self, prompt, system_prompt=None, json_schema=None, **kwargs
            ):
                return {"response": "test"}

            async def health_check(self):
                return True

            def get_provider_name(self):
                return "test"

            def get_provider_info(self):
                return {"provider": "test"}

        service = ConcreteLLMService(model="test-model")

        assert service.model == "test-model"
        assert service.temperature == 0.1
        assert service.max_tokens == 8192


class TestGeminiLLMService:
    """Tests for Gemini LLM service implementation."""

    @pytest.fixture()
    @pytest.fixture
    def mock_gemini_client(self):
        """Mock Gemini client."""
        with patch("app.services.llm_service.genai") as mock_genai:
            mock_client = Mock()
            mock_genai.GenerativeModel.return_value = mock_client
            yield mock_client

    @pytest.fixture()
    @pytest.fixture
    def gemini_service(self, mock_gemini_client):
        """Create Gemini service instance for testing."""
        return GeminiLLMService(
            api_key="test-api-key", model="gemini-1.5-pro", temperature=0.1, max_tokens=8192
        )

    def test_gemini_service_initialization(self, mock_gemini_client):
        """Test Gemini service initialization."""
        with patch("app.services.llm_service.genai") as mock_genai:
            service = GeminiLLMService(
                api_key="test-key", model="gemini-1.5-pro", temperature=0.2, max_tokens=4096
            )

            mock_genai.configure.assert_called_once_with(api_key="test-key")
            mock_genai.GenerativeModel.assert_called_once_with(model_name="gemini-1.5-pro")
            assert service.model == "gemini-1.5-pro"
            assert service.temperature == 0.2
            assert service.max_tokens == 4096

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_generate_content_success(self, gemini_service, mock_gemini_client):
        """Test successful content generation with Gemini."""
        # Setup mock response
        mock_response = Mock()
        mock_response.text = "Generated response text"
        mock_response.usage_metadata = {"tokens_used": 100}

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response

            result = await gemini_service.generate_content("Test prompt")

            assert result == {"response": "Generated response text", "usage": {"tokens_used": 100}}
            mock_to_thread.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_generate_content_with_system_prompt(
        self, gemini_service, mock_gemini_client
    ):
        """Test content generation with system prompt."""
        mock_response = Mock()
        mock_response.text = "Generated response"
        mock_response.usage_metadata = {}

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response

            await gemini_service.generate_content(
                prompt="User prompt", system_prompt="System instructions"
            )

            # Verify the combined prompt was used
            call_args = mock_to_thread.call_args
            combined_prompt = call_args[0][1]  # Second argument to generate_content
            assert "System instructions" in combined_prompt
            assert "User prompt" in combined_prompt

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_generate_json_content_success(self, gemini_service, mock_gemini_client):
        """Test successful JSON content generation."""
        test_json = {"key": "value", "number": 123}
        mock_response = Mock()
        mock_response.text = json.dumps(test_json)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response

            result = await gemini_service.generate_content(
                prompt="Generate JSON", json_schema={"type": "object"}
            )

            assert result == test_json

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_generate_json_from_markdown(self, gemini_service, mock_gemini_client):
        """Test JSON extraction from markdown code blocks."""
        test_json = {"extracted": "data"}
        mock_response = Mock()
        mock_response.text = f"Here's the JSON:\n```json\n{json.dumps(test_json)}\n```\nDone."

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response

            result = await gemini_service.generate_content(
                prompt="Generate JSON", json_schema={"type": "object"}
            )

            assert result == test_json

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_generate_invalid_json_response(self, gemini_service, mock_gemini_client):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.text = "This is not valid JSON"

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response

            result = await gemini_service.generate_content(
                prompt="Generate JSON", json_schema={"type": "object"}
            )

            assert result["error"] == "Invalid JSON response"
            assert result["raw_response"] == "This is not valid JSON"

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_quota_exceeded_error(self, gemini_service, mock_gemini_client):
        """Test quota exceeded error handling."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("Quota exceeded")

            with pytest.raises(LLMQuotaExceededError) as exc_info:
                await gemini_service.generate_content("Test prompt")

            assert "Gemini quota exceeded" in str(exc_info.value)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_rate_limit_error(self, gemini_service, mock_gemini_client):
        """Test rate limit error handling."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("Rate limit exceeded")

            with pytest.raises(LLMRateLimitError) as exc_info:
                await gemini_service.generate_content("Test prompt")

            assert "Gemini rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_gemini_generic_error(self, gemini_service, mock_gemini_client):
        """Test generic error handling."""
        # Mock the _generate_content_impl method to raise the expected exception
        expected_error = LLMError("Gemini generation failed: Generic error")

        with patch.object(
            gemini_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.side_effect = expected_error
    @pytest.mark.asyncio
    async def test_gemini_generic_error(self, gemini_service, mock_gemini_client):
        """Test generic error handling."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("Generic error")

            with pytest.raises(LLMError) as exc_info:
                await gemini_service.generate_content("Test prompt")

            assert "Gemini generation failed" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_gemini_health_check_success(self, gemini_service, mock_gemini_client):
        """Test successful health check."""
        # Mock the _generate_content_impl method instead of going through retry logic
        mock_response = {"response": "OK", "usage": {}}

        with patch.object(
            gemini_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.return_value = mock_response
    @pytest.mark.asyncio
    async def test_gemini_health_check_success(self, gemini_service, mock_gemini_client):
        """Test successful health check."""
        mock_response = Mock()
        mock_response.text = "OK"
        mock_response.usage_metadata = {}

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response

            result = await gemini_service.health_check()
            assert result is True

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_gemini_health_check_failure(self, gemini_service, mock_gemini_client):
        """Test health check failure."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = Exception("Connection failed")

            result = await gemini_service.health_check()
            assert result is False

    def test_gemini_get_provider_name(self, gemini_service):
        """Test provider name."""
        assert gemini_service.get_provider_name() == "gemini"

    def test_gemini_get_provider_info(self, gemini_service):
        """Test provider info."""
        info = gemini_service.get_provider_info()
        expected_info = {
            "provider": "gemini",
            "model": "gemini-1.5-pro",
            "endpoint": "https://generativelanguage.googleapis.com",
            "endpoint_type": "cloud",
            "location": "Google Cloud",
            "cost_model": "pay-per-token",
        }
        assert info == expected_info


class TestOpenAILLMService:
    """Tests for OpenAI LLM service implementation."""

    @pytest.fixture()
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        with patch("app.services.llm_service.openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            yield mock_client

    @pytest.fixture()
    @pytest.fixture
    def openai_service(self, mock_openai_client):
        """Create OpenAI service instance for testing."""
        return OpenAILLMService(
            api_key="test-api-key", model="gpt-4", temperature=0.1, max_tokens=8192
        )

    def test_openai_service_initialization(self, mock_openai_client):
        """Test OpenAI service initialization."""
        with patch("app.services.llm_service.openai.AsyncOpenAI") as mock_client_class:
            service = OpenAILLMService(
                api_key="test-key",
                model="gpt-4",
                temperature=0.2,
                max_tokens=4096,
                base_url="https://custom.openai.com",
            )

            mock_client_class.assert_called_once_with(
                api_key="test-key", base_url="https://custom.openai.com"
            )
            assert service.model == "gpt-4"
            assert service.temperature == 0.2
            assert service.max_tokens == 4096

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_openai_generate_content_success(self, openai_service, mock_openai_client):
        """Test successful content generation with OpenAI."""
        # Setup mock response
        mock_choice = Mock()
        mock_choice.message.content = "Generated response text"

        mock_usage = Mock()
        mock_usage.prompt_tokens = 50
        mock_usage.completion_tokens = 100
        mock_usage.total_tokens = 150

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await openai_service.generate_content("Test prompt")

        expected_result = {
            "response": "Generated response text",
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 100,
                "total_tokens": 150,
            },
        }
        assert result == expected_result

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_openai_generate_content_with_system_prompt(
        self, openai_service, mock_openai_client
    ):
        """Test content generation with system prompt."""
        mock_choice = Mock()
        mock_choice.message.content = "Response"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        await openai_service.generate_content(
            prompt="User prompt", system_prompt="System instructions"
        )

        # Verify messages structure
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System instructions"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User prompt"

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_openai_generate_json_content_success(self, openai_service, mock_openai_client):
        """Test successful JSON content generation."""
        test_json = {"key": "value", "number": 123}

        mock_choice = Mock()
        mock_choice.message.content = json.dumps(test_json)
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await openai_service.generate_content(
            prompt="Generate JSON", json_schema={"type": "object"}
        )

        assert result == test_json

        # Verify response format was set to JSON
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args[1]["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_openai_generate_invalid_json_response(self, openai_service, mock_openai_client):
        """Test handling of invalid JSON response."""
        mock_choice = Mock()
        mock_choice.message.content = "This is not valid JSON"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await openai_service.generate_content(
            prompt="Generate JSON", json_schema={"type": "object"}
        )

        assert result["error"] == "Invalid JSON response"
        assert result["raw_response"] == "This is not valid JSON"

    @pytest.mark.asyncio()
    async def test_openai_rate_limit_error(self, openai_service, mock_openai_client):
        """Test rate limit error handling."""
        # Create proper OpenAI RateLimitError with required arguments
        rate_limit_error = openai.RateLimitError(
            message="Rate limited", response=Mock(status_code=429, headers={}), body=None
        )
        mock_openai_client.chat.completions.create = AsyncMock(side_effect=rate_limit_error)
    @pytest.mark.asyncio
    async def test_openai_rate_limit_error(self, openai_service, mock_openai_client):
        """Test rate limit error handling."""
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError("Rate limited", response=None, body=None)
        )

        with pytest.raises(LLMRateLimitError) as exc_info:
            await openai_service.generate_content("Test prompt")

        assert "OpenAI rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_openai_connection_error(self, openai_service, mock_openai_client):
        """Test connection error handling."""
        # Create proper OpenAI APIConnectionError with request object
        connection_error = openai.APIConnectionError(message="Connection failed", request=Mock())
        mock_openai_client.chat.completions.create = AsyncMock(side_effect=connection_error)
    @pytest.mark.asyncio
    async def test_openai_connection_error(self, openai_service, mock_openai_client):
        """Test connection error handling."""
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=openai.APIConnectionError("Connection failed")
        )

        with pytest.raises(LLMError) as exc_info:
            await openai_service.generate_content("Test prompt")

        assert "OpenAI connection failed" in str(exc_info.value)

    @pytest.mark.asyncio()
        assert "OpenAI connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_openai_quota_exceeded_error(self, openai_service, mock_openai_client):
        """Test quota exceeded error handling."""
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Quota exceeded")
        )

        with pytest.raises(LLMQuotaExceededError) as exc_info:
            await openai_service.generate_content("Test prompt")

        assert "OpenAI quota exceeded" in str(exc_info.value)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_openai_generic_error(self, openai_service, mock_openai_client):
        """Test generic error handling."""
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Generic error")
        )

        with pytest.raises(LLMError) as exc_info:
            await openai_service.generate_content("Test prompt")

        assert "OpenAI generation failed" in str(exc_info.value)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_openai_health_check_success(self, openai_service, mock_openai_client):
        """Test successful health check."""
        mock_choice = Mock()
        mock_choice.message.content = "OK"
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(prompt_tokens=5, completion_tokens=5, total_tokens=10)

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await openai_service.health_check()
        assert result is True

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_openai_health_check_failure(self, openai_service, mock_openai_client):
        """Test health check failure."""
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        result = await openai_service.health_check()
        assert result is False

    def test_openai_get_provider_name(self, openai_service):
        """Test provider name."""
        assert openai_service.get_provider_name() == "openai"

    def test_openai_get_provider_info_cloud(self, openai_service):
        """Test provider info for cloud service."""
        openai_service.client.base_url = "https://api.openai.com"

        info = openai_service.get_provider_info()
        expected_info = {
            "provider": "openai",
            "model": "gpt-4",
            "endpoint": "https://api.openai.com",
            "endpoint_type": "cloud",
            "location": "OpenAI Cloud",
            "cost_model": "pay-per-token",
        }
        assert info == expected_info

    def test_openai_get_provider_info_local(self, openai_service):
        """Test provider info for local service."""
        openai_service.client.base_url = "http://localhost:8080"

        info = openai_service.get_provider_info()

        assert info["endpoint_type"] == "local"
        assert info["location"] == "Local server"
        assert info["cost_model"] == "free"


class TestOllamaLLMService:
    """Tests for Ollama LLM service implementation."""

    @pytest.fixture()
    @pytest.fixture
    def ollama_service(self):
        """Create Ollama service instance for testing."""
        return OllamaLLMService(
            base_url="http://localhost:11434",
            model="llama2",
            temperature=0.1,
            max_tokens=8192,
            timeout=300,
        )

    def test_ollama_service_initialization(self):
        """Test Ollama service initialization."""
        service = OllamaLLMService(
            base_url="http://localhost:11434/",  # Test URL normalization
            model="llama2",
            temperature=0.2,
            max_tokens=4096,
            timeout=120,
        )

        assert service.base_url == "http://localhost:11434"  # Trailing slash removed
        assert service.model == "llama2"
        assert service.temperature == 0.2
        assert service.max_tokens == 4096
        assert service.timeout == 120

    @pytest.mark.asyncio()
    async def test_ollama_generate_content_success(self, ollama_service):
        """Test successful content generation with Ollama."""
        expected_result = {
            "response": "Generated response text",
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 100,
                "total_tokens": 150,
                "total_duration": 5.0,
            },
        }

        # Mock the _generate_content_impl method directly to bypass aiohttp context manager issues
        with patch.object(
            ollama_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.return_value = expected_result

            result = await ollama_service.generate_content("Test prompt")
            assert result == expected_result

    @pytest.mark.asyncio()
    async def test_ollama_generate_content_with_system_prompt(self, ollama_service):
        """Test content generation with system prompt."""
        expected_result = {
            "response": "Response with system prompt",
            "usage": {
                "prompt_tokens": 60,
                "completion_tokens": 80,
                "total_tokens": 140,
                "total_duration": 3.0,
            },
        }

        # Mock the _generate_content_impl method and verify it's called with combined prompt
        with patch.object(
            ollama_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.return_value = expected_result

            result = await ollama_service.generate_content(
                prompt="User prompt", system_prompt="System instructions"
            )

            # Verify the implementation was called correctly
            mock_impl.assert_called_once_with(
                "User prompt",
                "System instructions",  # positional system_prompt
                None,  # positional json_schema
            )
            assert result == expected_result

    @pytest.mark.asyncio()
    async def test_ollama_generate_json_content_success(self, ollama_service):
        """Test successful JSON content generation."""
        test_json = {"key": "value", "number": 123}

        # Mock the _generate_content_impl method directly
        with patch.object(
            ollama_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.return_value = test_json
    @pytest.mark.asyncio
    async def test_ollama_generate_content_success(self, ollama_service):
        """Test successful content generation with Ollama."""
        mock_response_data = {
            "response": "Generated response text",
            "prompt_eval_count": 50,
            "eval_count": 100,
            "total_duration": 5000000000,  # 5 seconds in nanoseconds
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_response = mock_session.post.return_value.__aenter__.return_value
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)

            result = await ollama_service.generate_content("Test prompt")

            expected_result = {
                "response": "Generated response text",
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 100,
                    "total_tokens": 150,
                    "total_duration": 5.0,
                },
            }
            assert result == expected_result

    @pytest.mark.asyncio
    async def test_ollama_generate_content_with_system_prompt(self, ollama_service):
        """Test content generation with system prompt."""
        mock_response_data = {
            "response": "Response with system prompt",
            "prompt_eval_count": 60,
            "eval_count": 80,
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_response = mock_session.post.return_value.__aenter__.return_value
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)

            await ollama_service.generate_content(
                prompt="User prompt", system_prompt="System instructions"
            )

            # Verify the payload contains combined prompt
            call_args = mock_session.post.call_args
            payload = call_args[1]["json"]

            assert "System instructions" in payload["prompt"]
            assert "User prompt" in payload["prompt"]

    @pytest.mark.asyncio
    async def test_ollama_generate_json_content_success(self, ollama_service):
        """Test successful JSON content generation."""
        test_json = {"key": "value", "number": 123}
        mock_response_data = {
            "response": json.dumps(test_json),
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_response = mock_session.post.return_value.__aenter__.return_value
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)

            result = await ollama_service.generate_content(
                prompt="Generate JSON", json_schema={"type": "object"}
            )

            assert result == test_json
            # Verify the implementation was called with json_schema
            mock_impl.assert_called_once_with(
                "Generate JSON",
                None,  # positional system_prompt
                {"type": "object"},  # positional json_schema
            )

    @pytest.mark.asyncio()
    async def test_ollama_generate_invalid_json_response(self, ollama_service):
        """Test handling of invalid JSON response."""
        expected_result = {
            "error": "Invalid JSON response",
            "raw_response": "This is not valid JSON",
        }

        # Mock the _generate_content_impl method directly
        with patch.object(
            ollama_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.return_value = expected_result

            # Verify JSON instruction was added to prompt
            call_args = mock_session.post.call_args
            payload = call_args[1]["json"]
            assert "valid JSON only" in payload["prompt"]

    @pytest.mark.asyncio
    async def test_ollama_generate_invalid_json_response(self, ollama_service):
        """Test handling of invalid JSON response."""
        mock_response_data = {
            "response": "This is not valid JSON",
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_response = mock_session.post.return_value.__aenter__.return_value
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)

            result = await ollama_service.generate_content(
                prompt="Generate JSON", json_schema={"type": "object"}
            )

            assert result["error"] == "Invalid JSON response"
            assert result["raw_response"] == "This is not valid JSON"

    @pytest.mark.asyncio()
    async def test_ollama_api_error_response(self, ollama_service):
        """Test API error response handling."""
        # Mock the _generate_content_impl method to raise the expected exception
        expected_error = LLMError("Ollama API error 500: Internal server error")

        with patch.object(
            ollama_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.side_effect = expected_error
    @pytest.mark.asyncio
    async def test_ollama_api_error_response(self, ollama_service):
        """Test API error response handling."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_response = mock_session.post.return_value.__aenter__.return_value
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal server error")

            with pytest.raises(LLMError) as exc_info:
                await ollama_service.generate_content("Test prompt")

            assert "Ollama API error 500" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_ollama_timeout_error(self, ollama_service):
        """Test timeout error handling."""
        # Mock the _generate_content_impl method to raise the expected timeout exception
        expected_error = LLMError("Ollama request timed out after 300 seconds")

        with patch.object(
            ollama_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.side_effect = expected_error
    @pytest.mark.asyncio
    async def test_ollama_timeout_error(self, ollama_service):
        """Test timeout error handling."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_session.post.side_effect = asyncio.TimeoutError()

            with pytest.raises(LLMError) as exc_info:
                await ollama_service.generate_content("Test prompt")

            assert "timed out after 300 seconds" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_ollama_connection_error(self, ollama_service):
        """Test connection error handling."""
        from app.core.exceptions import OllamaConnectionError

        # Mock the _generate_content_impl method to raise the expected connection exception
        expected_error = OllamaConnectionError("http://localhost:11434", "Connection failed")

        with patch.object(
            ollama_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.side_effect = expected_error
    @pytest.mark.asyncio
    async def test_ollama_connection_error(self, ollama_service):
        """Test connection error handling."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_session.post.side_effect = aiohttp.ClientError("Connection failed")

            with pytest.raises(LLMError) as exc_info:
                await ollama_service.generate_content("Test prompt")

            assert "Ollama connection failed" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_ollama_generic_error(self, ollama_service):
        """Test generic error handling."""
        # Mock the _generate_content_impl method to raise the expected generic exception
        expected_error = LLMError("Ollama generation failed: Generic error")

        with patch.object(
            ollama_service, "_generate_content_impl", new_callable=AsyncMock
        ) as mock_impl:
            mock_impl.side_effect = expected_error
            assert "Ollama connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ollama_generic_error(self, ollama_service):
        """Test generic error handling."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_session.post.side_effect = Exception("Generic error")

            with pytest.raises(LLMError) as exc_info:
                await ollama_service.generate_content("Test prompt")

            assert "Ollama generation failed" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_ollama_health_check_success(self, ollama_service):
        """Test successful health check."""
        # Create proper mock for aiohttp session context managers
        mock_response = Mock()
        mock_response.status = 200

        # Create an async context manager mock
        mock_response_context = AsyncMock()
        mock_response_context.__aenter__.return_value = mock_response

        mock_session = Mock()
        mock_session.get.return_value = mock_response_context

        # Create session context manager mock
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.return_value = mock_session

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session_context
    @pytest.mark.asyncio
    async def test_ollama_health_check_success(self, ollama_service):
        """Test successful health check."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_response = mock_session.get.return_value.__aenter__.return_value
            mock_response.status = 200

            result = await ollama_service.health_check()
            assert result is True

            # Verify correct endpoint was called
            mock_session.get.assert_called_once_with("http://localhost:11434/api/tags")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_ollama_health_check_failure(self, ollama_service):
        """Test health check failure."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = mock_session_class.return_value.__aenter__.return_value
            mock_session.get.side_effect = Exception("Connection failed")

            result = await ollama_service.health_check()
            assert result is False

    def test_ollama_get_provider_name(self, ollama_service):
        """Test provider name."""
        assert ollama_service.get_provider_name() == "ollama"

    def test_ollama_get_provider_info_local(self, ollama_service):
        """Test provider info for local service."""
        info = ollama_service.get_provider_info()
        expected_info = {
            "provider": "ollama",
            "model": "llama2",
            "endpoint": "http://localhost:11434",
            "endpoint_type": "local",
            "location": "Local machine",
            "cost_model": "free",
            "timeout": "300s",
        }
        assert info == expected_info

    def test_ollama_get_provider_info_remote(self):
        """Test provider info for remote service."""
        service = OllamaLLMService(base_url="http://remote-server.com:11434", model="llama2")

        info = service.get_provider_info()
        assert info["endpoint_type"] == "remote"
        assert info["location"] == "Remote server (http://remote-server.com:11434)"


class TestLLMServiceFactory:
    """Tests for LLM service factory."""

    def test_create_gemini_service(self):
        """Test creating Gemini service via factory."""
        with patch("app.services.llm_service.settings") as mock_settings, patch(
            "app.services.llm_service.genai"
        ):
            mock_settings.llm_provider = "gemini"
            mock_settings.llm_model = "gemini-1.5-pro"
            mock_settings.llm_temperature = 0.2
            mock_settings.llm_max_tokens = 4096
            mock_settings.google_api_key = "test-key"

            service = LLMServiceFactory.create_llm_service()

            assert isinstance(service, GeminiLLMService)
            assert service.model == "gemini-1.5-pro"
            assert service.temperature == 0.2
            assert service.max_tokens == 4096

    def test_create_openai_service(self):
        """Test creating OpenAI service via factory."""
        with patch("app.services.llm_service.settings") as mock_settings, patch(
            "app.services.llm_service.openai.AsyncOpenAI"
        ):
            mock_settings.llm_provider = "openai"
            mock_settings.llm_model = "gpt-4"
            mock_settings.llm_temperature = 0.1
            mock_settings.llm_max_tokens = 8192
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = None

            service = LLMServiceFactory.create_llm_service()

            assert isinstance(service, OpenAILLMService)
            assert service.model == "gpt-4"

    def test_create_ollama_service(self):
        """Test creating Ollama service via factory."""
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.llm_provider = "ollama"
            mock_settings.llm_model = "llama2"
            mock_settings.llm_temperature = 0.0
            mock_settings.llm_max_tokens = 4096
            mock_settings.ollama_base_url = "http://localhost:11434"
            mock_settings.ollama_timeout = 120

            service = LLMServiceFactory.create_llm_service()

            assert isinstance(service, OllamaLLMService)
            assert service.model == "llama2"
            assert service.timeout == 120

    def test_create_service_missing_gemini_api_key(self):
        """Test error when Gemini API key is missing."""
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.llm_provider = "gemini"
            mock_settings.google_api_key = None

            with pytest.raises(ValueError, match="Google API key is required"):
                LLMServiceFactory.create_llm_service()

            with pytest.raises(ValueError) as exc_info:
                LLMServiceFactory.create_llm_service()

            assert "Google API key is required" in str(exc_info.value)

    def test_create_service_missing_openai_api_key(self):
        """Test error when OpenAI API key is missing."""
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.openai_api_key = None

            with pytest.raises(ValueError, match="OpenAI API key is required"):
                LLMServiceFactory.create_llm_service()

            with pytest.raises(ValueError) as exc_info:
                LLMServiceFactory.create_llm_service()

            assert "OpenAI API key is required" in str(exc_info.value)

    def test_create_service_unsupported_provider(self):
        """Test error for unsupported provider."""
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.llm_provider = "unsupported"

            with pytest.raises(ValueError, match="Unsupported LLM provider: unsupported"):
                LLMServiceFactory.create_llm_service()

            with pytest.raises(ValueError) as exc_info:
                LLMServiceFactory.create_llm_service()

            assert "Unsupported LLM provider: unsupported" in str(exc_info.value)


class TestGetLLMService:
    """Tests for get_llm_service convenience function."""

    def test_get_llm_service_calls_factory(self):
        """Test that get_llm_service calls the factory."""
        with patch("app.services.llm_service.LLMServiceFactory.create_llm_service") as mock_factory:
            mock_service = Mock()
            mock_factory.return_value = mock_service

            result = get_llm_service()

            assert result == mock_service
            mock_factory.assert_called_once()
