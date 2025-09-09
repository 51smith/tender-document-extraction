"""
Abstract LLM service interface and concrete implementations for different providers.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod

from typing import Any, Dict, List, Optional, Union

import aiohttp
import openai
from google import generativeai as genai

from app.config import settings
from app.core.exceptions import (
    LLMError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    OllamaConnectionError,
    OpenAIConnectionError,
    OpenAIRateLimitError,
)
from app.core.retry_config import get_retry_manager

logger = logging.getLogger(__name__)


class BaseLLMService(ABC):
    """Abstract base class for LLM services."""

    def __init__(self, model: str, temperature: float = 0.1, max_tokens: int = 8192):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.retry_manager = get_retry_manager()

    @abstractmethod
    async def _generate_content_impl(
        self,
        prompt: str,

    async def generate_content(
        self,
        prompt: str,
        """Generate content using the LLM provider with retry logic."""
        return await self.retry_manager.execute_with_retry(
            self._generate_content_impl,
            self.get_provider_name(),
            prompt,
            system_prompt,
            json_schema,
            **kwargs,
        )

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM service is healthy."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name."""
    def reset_circuit_breaker(self):
        """Reset circuit breaker for this provider."""
        self.retry_manager.reset_circuit_breaker(self.get_provider_name())


class GeminiLLMService(BaseLLMService):
    """Google Gemini LLM service implementation."""

    def __init__(self, api_key: str, model: str, temperature: float = 0.1, max_tokens: int = 8192):
        super().__init__(model, temperature, max_tokens)
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model_name=model)

    async def _generate_content_impl(
        self,
        prompt: str,
        """Generate content using Gemini API."""
        try:
            # Build the full prompt
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            generation_config = genai.types.GenerationConfig(
                temperature=self.temperature, max_output_tokens=self.max_tokens
            )

            # Generate content
            response = await asyncio.to_thread(
                self.client.generate_content, full_prompt, generation_config=generation_config
            )

            # Parse response
            response_text = response.text.strip()

            if json_schema:
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                        try:
                            return json.loads(json_text)
                        except json.JSONDecodeError:
                            pass
                    logger.warning(f"Failed to parse JSON response: {response_text}")
                    return {"error": "Invalid JSON response", "raw_response": response_text}

            # Get usage metadata if available
            usage_info = {}
            if hasattr(response, "usage_metadata"):
                usage_info = response.usage_metadata
            elif hasattr(response, "prompt_feedback"):
                usage_info = {"prompt_feedback": response.prompt_feedback}

            return {"response": response_text, "usage": usage_info}

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            if "quota" in str(e).lower():
                raise LLMQuotaExceededError(f"Gemini quota exceeded: {e}")
            elif "rate limit" in str(e).lower():
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            else:
                raise LLMError(f"Gemini generation failed: {e}")

    async def health_check(self) -> bool:
        """Check Gemini API health."""
        try:
            response = await self.generate_content("Hello, respond with 'OK'")
            return "OK" in response.get("response", "")
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False

    def get_provider_name(self) -> str:
        return "gemini"

        return {
            "provider": "gemini",
            "model": self.model,
            "endpoint": "https://generativelanguage.googleapis.com",
            "endpoint_type": "cloud",
            "location": "Google Cloud",
            "cost_model": "pay-per-token",
        }


class OpenAILLMService(BaseLLMService):
    """OpenAI LLM service implementation."""

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ):
        super().__init__(model, temperature, max_tokens)
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def _generate_content_impl(
        self,
        prompt: str,
        """Generate content using OpenAI API."""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Configure response format
            response_format = {"type": "json_object"} if json_schema else {"type": "text"}

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format=response_format,
            )

            response_text = response.choices[0].message.content.strip()

            if json_schema:
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                        try:
                            return json.loads(json_text)
                        except json.JSONDecodeError:
                            pass
                    logger.warning(f"Failed to parse JSON response: {response_text}")
                    return {"error": "Invalid JSON response", "raw_response": response_text}

            return {
                "response": response_text,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }

            raise OpenAIRateLimitError()
        except openai.APIConnectionError as e:
            raise OpenAIConnectionError(str(e))
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            if "quota" in str(e).lower():
                raise LLMQuotaExceededError(f"OpenAI quota exceeded: {e}")
            else:
                raise LLMError(f"OpenAI generation failed: {e}")

    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            response = await self.generate_content("Hello, respond with 'OK'")
            return "OK" in response.get("response", "")
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False

    def get_provider_name(self) -> str:
        return "openai"

        base_url = (
            self.client.base_url if hasattr(self.client, "base_url") else "https://api.openai.com"
        )
        is_local = "localhost" in str(base_url) or "127.0.0.1" in str(base_url)

        return {
            "provider": "openai",
            "model": self.model,
            "endpoint": str(base_url),
            "endpoint_type": "local" if is_local else "cloud",
            "location": "Local server" if is_local else "OpenAI Cloud",
            "cost_model": "free" if is_local else "pay-per-token",
        }


class OllamaLLMService(BaseLLMService):
    """Ollama LLM service implementation."""

    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 8192,
        timeout: int = 300,
    ):
        super().__init__(model, temperature, max_tokens)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _generate_content_impl(
        self,
        prompt: str,
        """Generate content using Ollama API."""
        try:
            # Build the full prompt
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            if json_schema:
                full_prompt += "\n\nPlease respond with valid JSON only."

            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
            }

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)

        except asyncio.TimeoutError:
            raise LLMError(f"Ollama request timed out after {self.timeout} seconds")
        except aiohttp.ClientError as e:
            raise OllamaConnectionError(self.base_url, str(e))
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise LLMError(f"Ollama generation failed: {e}")

    async def health_check(self) -> bool:
        """Check Ollama API health."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    def get_provider_name(self) -> str:
        return "ollama"

        is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url

        return {
            "provider": "ollama",
            "model": self.model,
            "endpoint": self.base_url,
            "endpoint_type": "local" if is_local else "remote",
            "location": "Local machine" if is_local else f"Remote server ({self.base_url})",
            "cost_model": "free",
            "timeout": f"{self.timeout}s",
        }


class LLMServiceFactory:
    """Factory class to create LLM service instances."""

    @staticmethod
    def create_llm_service() -> BaseLLMService:
        """Create an LLM service instance based on configuration."""
        provider = settings.llm_provider
        model = settings.llm_model
        temperature = settings.llm_temperature
        max_tokens = settings.llm_max_tokens

        if provider == "gemini":
            if not settings.google_api_key:
                raise ValueError("Google API key is required for Gemini provider")
            return GeminiLLMService(
                api_key=settings.google_api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        elif provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key is required for OpenAI provider")
            return OpenAILLMService(
                api_key=settings.openai_api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                base_url=settings.openai_base_url,
            )
        elif provider == "ollama":
            return OllamaLLMService(
                base_url=settings.ollama_base_url,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=settings.ollama_timeout,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")


# Convenience function to get LLM service
def get_llm_service() -> BaseLLMService:
    """Get the configured LLM service instance."""
    return LLMServiceFactory.create_llm_service()
