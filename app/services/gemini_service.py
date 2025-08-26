import asyncio
import io
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import google.generativeai as genai
from google import genai as genai_client
from google.api_core import exceptions as google_exceptions
from google.generativeai.types import HarmBlockThreshold, HarmCategory

from app.config import settings
from app.core.exceptions import (
    GeminiAPIException,
    GeminiModelError,
    GeminiQuotaExceededError,
    GeminiRateLimitError,
    ServiceUnavailableError,
)
from app.core.rate_limiter import get_rate_limiter
from app.services.llm_service import get_llm_service, BaseLLMService

logger = logging.getLogger(__name__)


class GeminiClient:
    """Google Gemini API client with rate limiting and error handling."""

    def __init__(self):
        self.settings = settings
        self.rate_limiter = get_rate_limiter()
        self._client = None
        self._file_client = None
        self._model = None
        self._llm_service: Optional[BaseLLMService] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Gemini client."""
        try:
            # Initialize the new configurable LLM service
            self._llm_service = get_llm_service()
            
            # Keep legacy Gemini-specific initialization for file uploads if using Gemini
            if settings.llm_provider == "gemini":
                genai.configure(api_key=self.settings.google_api_key)

                # Configure safety settings for document processing
                safety_settings = [
                    {
                        "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        "threshold": HarmBlockThreshold.BLOCK_NONE,
                    },
                    {
                        "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                    {
                        "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                    {
                        "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                ]

                # Configure generation parameters
                generation_config = genai.types.GenerationConfig(
                    temperature=self.settings.llm_temperature,
                    top_p=0.9,
                    top_k=40,
                    max_output_tokens=self.settings.llm_max_tokens,
                )

                self._model = genai.GenerativeModel(
                    model_name=self.settings.llm_model,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )

                # Initialize the new client for file uploads
                self._file_client = genai_client.Client(api_key=self.settings.google_api_key)

            logger.info(f"LLM client initialized with provider: {settings.llm_provider}, model: {settings.llm_model}")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise ServiceUnavailableError(f"Failed to initialize AI service: {str(e)}")

    def _estimate_tokens(self, content: Union[str, List[Any]]) -> int:
        """Estimate token count for content."""
        if isinstance(content, str):
            # Rough estimation: 1 token ≈ 4 characters for English text
            return max(len(content) // 4, 100)
        elif isinstance(content, list):
            # For multimodal content, sum up text parts and add overhead for images
            total = 0
            for item in content:
                if isinstance(item, str):
                    total += len(item) // 4
                elif hasattr(item, "mime_type") and item.mime_type.startswith("image/"):
                    total += 1000  # Rough estimate for image tokens
                else:
                    total += 100  # Default overhead
            return max(total, 100)
        else:
            return 1000  # Default conservative estimate

    async def generate_content(
        self, prompt: Union[str, List[Any]], timeout: float = 120.0, retry_attempts: int = 3
    ) -> Dict[str, Any]:
        """Generate content using Gemini API with rate limiting and error handling."""

        estimated_tokens = self._estimate_tokens(prompt)

        # Wait for rate limit capacity
        await self.rate_limiter.wait_for_capacity(estimated_tokens)

        last_exception = None

        for attempt in range(retry_attempts):
            try:
                start_time = time.time()

                # Make the API call
                response = await asyncio.wait_for(
                    self._generate_content_async(prompt), timeout=timeout
                )

                processing_time = time.time() - start_time

                # Record actual token usage
                actual_tokens = self._get_token_count_from_response(response)
                self.rate_limiter.record_token_usage(actual_tokens)

                # Parse and validate JSON response
                result = self._parse_response(response)

                # Add metadata
                result["_metadata"] = {
                    "model": self.settings.llm_model,
                    "processing_time": processing_time,
                    "estimated_tokens": estimated_tokens,
                    "actual_tokens": actual_tokens,
                    "attempt": attempt + 1,
                    "timestamp": time.time(),
                }

                logger.info(
                    f"Successful Gemini API call: {actual_tokens} tokens, {processing_time:.2f}s"
                )
                return result

            except asyncio.TimeoutError:
                last_exception = GeminiAPIException(f"Request timed out after {timeout}s")
                logger.warning(f"Attempt {attempt + 1}: Request timeout")

            except google_exceptions.ResourceExhausted as e:
                if "quota" in str(e).lower():
                    raise GeminiQuotaExceededError()
                else:
                    last_exception = GeminiRateLimitError()
                    # Exponential backoff for rate limits
                    wait_time = (2**attempt) * 1.0
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                    await asyncio.sleep(wait_time)

            except google_exceptions.InvalidArgument as e:
                # Don't retry invalid arguments
                raise GeminiModelError(str(e), self.settings.llm_model)

            except google_exceptions.GoogleAPICallError as e:
                last_exception = GeminiAPIException(f"Google API error: {str(e)}")
                logger.warning(f"Attempt {attempt + 1}: Google API error: {e}")

                # Exponential backoff for API errors
                wait_time = (2**attempt) * 0.5
                await asyncio.sleep(wait_time)

            except Exception as e:
                last_exception = GeminiAPIException(f"Unexpected error: {str(e)}")
                logger.error(f"Attempt {attempt + 1}: Unexpected error: {e}")

                # Short wait for unexpected errors
                await asyncio.sleep(1.0)

        # All attempts failed
        logger.error(f"All {retry_attempts} attempts failed for Gemini API call")
        raise last_exception or GeminiAPIException("All retry attempts failed")

    async def _generate_content_async(self, prompt: Union[str, List[Any]]) -> Any:
        """Make async API call to Gemini."""
        try:
            # Run the synchronous API call in a thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._model.generate_content, prompt)
        except Exception as e:
            logger.error(f"Error in _generate_content_async: {e}")
            raise

    def _get_token_count_from_response(self, response: Any) -> int:
        """Extract token count from API response."""
        try:
            if hasattr(response, "usage_metadata"):
                return getattr(response.usage_metadata, "total_token_count", 0)
            return 0
        except Exception:
            return 0  # Fallback if we can't get token count

    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse and validate Gemini response."""
        try:
            # Debug: Log response details
            logger.info(f"Response object type: {type(response)}")
            logger.info(f"Response has text attribute: {hasattr(response, 'text')}")
            if hasattr(response, "text"):
                logger.info(f"Response.text is None: {response.text is None}")
                logger.info(f"Response.text length: {len(response.text) if response.text else 0}")
                if response.text:
                    logger.info(f"Response.text preview: {repr(response.text[:200])}")

            if not response or not response.text:
                logger.error(f"Empty response from Gemini API. Response: {response}")
                raise GeminiModelError("Empty response from Gemini API", self.settings.llm_model)

            # Try to parse as JSON
            try:
                result = json.loads(response.text.strip())
                logger.info("Successfully parsed JSON response")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                logger.warning(f"Raw response length: {len(response.text)}")
                logger.warning(f"Raw response: {repr(response.text[:500])}...")

                # Try to extract JSON from markdown code blocks
                text = response.text.strip()
                logger.info(
                    f"Looking for JSON in markdown. Contains '```json': {'```json' in text}"
                )
                if "```json" in text and "```" in text:
                    start = text.find("```json") + 7
                    end = text.find("```", start)
                    json_text = text[start:end].strip()
                    logger.info(f"Extracted JSON text length: {len(json_text)}")
                    logger.info(f"JSON text preview: {repr(json_text[:200])}")
                    try:
                        result = json.loads(json_text)
                        logger.info("Successfully parsed JSON from markdown")
                        return result
                    except json.JSONDecodeError as markdown_e:
                        logger.warning(f"Failed to parse JSON from markdown: {markdown_e}")
                        pass

                # Return raw text if JSON parsing fails
                return {
                    "raw_response": response.text,
                    "parse_error": str(e),
                    "extraction_success": False,
                }

        except Exception as e:
            raise GeminiModelError(
                f"Failed to parse response: {str(e)}", self.settings.llm_model
            )

    async def test_connection(self) -> Dict[str, Any]:
        """Test the LLM API connection."""
        try:
            # Test the new LLM service health check
            if await self._llm_service.health_check():
                provider_info = self._llm_service.get_provider_info()
                result = {
                    "status": "success",
                    "message": f"{settings.llm_provider} connection successful",
                }
                result.update(provider_info)
                return result
            else:
                provider_info = self._llm_service.get_provider_info()
                result = {
                    "status": "error",
                    "error": "Health check failed",
                }
                result.update(provider_info)
                return result

        except Exception as e:
            return {"status": "error", "error": str(e), "error_type": type(e).__name__}

    async def process_multiple_documents(
        self,
        documents: Dict[str, bytes],
        prompt: str,
        timeout: float = 180.0,
        retry_attempts: int = 3,
    ) -> Dict[str, Any]:
        """Process multiple documents in a single API call using File API."""
        
        # Only process with Gemini if the provider is actually Gemini
        if settings.llm_provider != "gemini":
            raise ValueError(f"Multi-document processing with File API only available for Gemini provider, current provider is {settings.llm_provider}")

        uploaded_files = []

        try:
            # Upload all documents to Gemini File API
            logger.info(f"Uploading {len(documents)} documents to Gemini File API")

            for filename, content in documents.items():
                logger.info(f"Uploading document: {filename}")

                # Create file data stream
                file_data = io.BytesIO(content)

                # Determine MIME type based on file extension
                mime_type = self._get_mime_type(filename)

                # Upload file using the new client
                uploaded_file = self._file_client.files.upload(
                    file=file_data, config=dict(mime_type=mime_type, display_name=filename)
                )

                uploaded_files.append(uploaded_file)
                logger.info(f"Successfully uploaded {filename} with ID: {uploaded_file.name}")

            # Estimate tokens for all documents
            estimated_tokens = (
                sum(len(content) // 4 for content in documents.values()) + len(prompt) // 4
            )

            # Wait for rate limit capacity
            await self.rate_limiter.wait_for_capacity(estimated_tokens)

            # Prepare content for the API call
            contents = uploaded_files + [prompt]

            last_exception = None

            for attempt in range(retry_attempts):
                try:
                    start_time = time.time()

                    # Make the API call with multiple uploaded files
                    response = await asyncio.wait_for(
                        self._generate_multi_document_content_async(contents), timeout=timeout
                    )

                    processing_time = time.time() - start_time

                    # Record actual token usage
                    actual_tokens = self._get_token_count_from_response(response)
                    self.rate_limiter.record_token_usage(actual_tokens)

                    # Parse and validate response
                    result = self._parse_response(response)

                    # Add metadata
                    result["_metadata"] = {
                        "model": self.settings.llm_model,
                        "processing_time": processing_time,
                        "estimated_tokens": estimated_tokens,
                        "actual_tokens": actual_tokens,
                        "attempt": attempt + 1,
                        "timestamp": time.time(),
                        "num_documents": len(documents),
                        "uploaded_files": [f.name for f in uploaded_files],
                    }

                    logger.info(
                        f"Successfully processed {len(documents)} documents: {actual_tokens} tokens, {processing_time:.2f}s"
                    )
                    return result

                except asyncio.TimeoutError:
                    last_exception = GeminiAPIException(
                        f"Multi-document request timed out after {timeout}s"
                    )
                    logger.warning(f"Attempt {attempt + 1}: Request timeout")

                except google_exceptions.ResourceExhausted as e:
                    if "quota" in str(e).lower():
                        raise GeminiQuotaExceededError()
                    else:
                        last_exception = GeminiRateLimitError()
                        wait_time = (2**attempt) * 1.0
                        logger.warning(
                            f"Rate limited, waiting {wait_time}s before retry {attempt + 1}"
                        )
                        await asyncio.sleep(wait_time)

                except google_exceptions.InvalidArgument as e:
                    raise GeminiModelError(str(e), self.settings.llm_model)

                except google_exceptions.GoogleAPICallError as e:
                    last_exception = GeminiAPIException(f"Google API error: {str(e)}")
                    logger.warning(f"Attempt {attempt + 1}: Google API error: {e}")
                    wait_time = (2**attempt) * 0.5
                    await asyncio.sleep(wait_time)

                except Exception as e:
                    last_exception = GeminiAPIException(f"Unexpected error: {str(e)}")
                    logger.error(f"Attempt {attempt + 1}: Unexpected error: {e}")
                    await asyncio.sleep(1.0)

            # All attempts failed
            logger.error(f"All {retry_attempts} attempts failed for multi-document API call")
            raise last_exception or GeminiAPIException("All retry attempts failed")

        finally:
            # Clean up uploaded files
            for uploaded_file in uploaded_files:
                try:
                    self._file_client.files.delete(name=uploaded_file.name)
                    logger.info(f"Deleted uploaded file: {uploaded_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete uploaded file {uploaded_file.name}: {e}")

    def _get_mime_type(self, filename: str) -> str:
        """Determine MIME type based on file extension."""
        extension = filename.lower().split(".")[-1]

        mime_types = {
            "pdf": "application/pdf",
            "txt": "text/plain",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "html": "text/html",
            "htm": "text/html",
        }

        return mime_types.get(extension, "application/octet-stream")

    async def _generate_multi_document_content_async(self, contents: List[Any]) -> Any:
        """Make async API call to Gemini with multiple documents."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._file_client.models.generate_content(
                    model=self.settings.llm_model, contents=contents
                ),
            )
        except Exception as e:
            logger.error(f"Error in _generate_multi_document_content_async: {e}")
            raise

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return {
            "rate_limits": self.rate_limiter.get_current_limits(),
            "stats": self.rate_limiter.get_stats(),
            "provider": settings.llm_provider,
            "model": settings.llm_model,
        }


# Global client instance
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get the global Gemini client instance."""
    global _gemini_client

    if _gemini_client is None:
        _gemini_client = GeminiClient()

    return _gemini_client


def reset_gemini_client() -> None:
    """Reset the global client (useful for testing)."""
    global _gemini_client
    _gemini_client = None
