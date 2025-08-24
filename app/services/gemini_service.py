import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core import exceptions as google_exceptions

from app.config import settings
from app.core.exceptions import (
    GeminiAPIException,
    GeminiRateLimitError,
    GeminiQuotaExceededError,
    GeminiModelError,
    ServiceUnavailableError
)
from app.core.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class GeminiClient:
    """Google Gemini API client with rate limiting and error handling."""
    
    def __init__(self):
        self.settings = settings.gemini
        self.rate_limiter = get_rate_limiter()
        self._client = None
        self._model = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the Gemini client."""
        try:
            genai.configure(api_key=self.settings.api_key)
            
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
                temperature=self.settings.temperature,
                top_p=0.9,
                top_k=40,
                max_output_tokens=self.settings.max_tokens,
                response_mime_type="application/json"
            )
            
            self._model = genai.GenerativeModel(
                model_name=self.settings.model,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            logger.info(f"Gemini client initialized with model: {self.settings.model}")
            
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
                elif hasattr(item, 'mime_type') and item.mime_type.startswith('image/'):
                    total += 1000  # Rough estimate for image tokens
                else:
                    total += 100  # Default overhead
            return max(total, 100)
        else:
            return 1000  # Default conservative estimate
    
    async def generate_content(
        self,
        prompt: Union[str, List[Any]],
        timeout: float = 120.0,
        retry_attempts: int = 3
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
                    self._generate_content_async(prompt),
                    timeout=timeout
                )
                
                processing_time = time.time() - start_time
                
                # Record actual token usage
                actual_tokens = self._get_token_count_from_response(response)
                self.rate_limiter.record_token_usage(actual_tokens)
                
                # Parse and validate JSON response
                result = self._parse_response(response)
                
                # Add metadata
                result["_metadata"] = {
                    "model": self.settings.model,
                    "processing_time": processing_time,
                    "estimated_tokens": estimated_tokens,
                    "actual_tokens": actual_tokens,
                    "attempt": attempt + 1,
                    "timestamp": time.time()
                }
                
                logger.info(f"Successful Gemini API call: {actual_tokens} tokens, {processing_time:.2f}s")
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
                    wait_time = (2 ** attempt) * 1.0
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                    await asyncio.sleep(wait_time)
                
            except google_exceptions.InvalidArgument as e:
                # Don't retry invalid arguments
                raise GeminiModelError(str(e), self.settings.model)
                
            except google_exceptions.GoogleAPICallError as e:
                last_exception = GeminiAPIException(f"Google API error: {str(e)}")
                logger.warning(f"Attempt {attempt + 1}: Google API error: {e}")
                
                # Exponential backoff for API errors
                wait_time = (2 ** attempt) * 0.5
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
            return await loop.run_in_executor(
                None,
                self._model.generate_content,
                prompt
            )
        except Exception as e:
            logger.error(f"Error in _generate_content_async: {e}")
            raise
    
    def _get_token_count_from_response(self, response: Any) -> int:
        """Extract token count from API response."""
        try:
            if hasattr(response, 'usage_metadata'):
                return getattr(response.usage_metadata, 'total_token_count', 0)
            return 0
        except Exception:
            return 0  # Fallback if we can't get token count
    
    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse and validate Gemini response."""
        try:
            if not response or not response.text:
                raise GeminiModelError("Empty response from Gemini API", self.settings.model)
            
            # Try to parse as JSON
            try:
                result = json.loads(response.text.strip())
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                logger.debug(f"Raw response: {response.text[:500]}...")
                
                # Try to extract JSON from markdown code blocks
                text = response.text.strip()
                if "```json" in text and "```" in text:
                    start = text.find("```json") + 7
                    end = text.find("```", start)
                    json_text = text[start:end].strip()
                    try:
                        return json.loads(json_text)
                    except json.JSONDecodeError:
                        pass
                
                # Return raw text if JSON parsing fails
                return {
                    "raw_response": response.text,
                    "parse_error": str(e),
                    "extraction_success": False
                }
                
        except Exception as e:
            raise GeminiModelError(f"Failed to parse response: {str(e)}", self.settings.model)
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the Gemini API connection."""
        try:
            test_prompt = "Please respond with a JSON object: {'test': true, 'message': 'Connection successful'}"
            
            result = await self.generate_content(test_prompt, timeout=30.0, retry_attempts=1)
            
            return {
                "status": "success",
                "model": self.settings.model,
                "response": result,
                "rate_limits": self.rate_limiter.get_current_limits()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        return {
            "rate_limits": self.rate_limiter.get_current_limits(),
            "stats": self.rate_limiter.get_stats(),
            "model": self.settings.model
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