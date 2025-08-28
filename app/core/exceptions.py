from typing import Any, Dict, Optional

from fastapi import HTTPException
from starlette import status


class TenderExtractionException(Exception):
    """Base exception for tender extraction service."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message
        self.details = details or {}
        self.error_code = error_code
        super().__init__(self.message)


class GeminiAPIException(TenderExtractionException):
    """Exception for Google Gemini API errors."""

    pass


class GeminiRateLimitError(GeminiAPIException):
    """Rate limit exceeded for Gemini API."""

    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(
            "Gemini API rate limit exceeded",
            details={"retry_after": retry_after},
            error_code="GEMINI_RATE_LIMIT",
        )


class GeminiQuotaExceededError(GeminiAPIException):
    """Quota exceeded for Gemini API."""

    def __init__(self, quota_type: str = "monthly"):
        self.quota_type = quota_type
        super().__init__(
            f"Gemini API {quota_type} quota exceeded",
            details={"quota_type": quota_type},
            error_code="GEMINI_QUOTA_EXCEEDED",
        )


class GeminiModelError(GeminiAPIException):
    """Model-specific error from Gemini API."""

    def __init__(self, model_error: str, model_name: str):
        self.model_error = model_error
        self.model_name = model_name
        super().__init__(
            f"Gemini model error: {model_error}",
            details={"model_error": model_error, "model_name": model_name},
            error_code="GEMINI_MODEL_ERROR",
        )


class DocumentProcessingError(TenderExtractionException):
    """Document processing specific errors."""

    pass


class DocumentTooLargeError(DocumentProcessingError):
    """Document exceeds maximum size limit."""

    def __init__(self, file_size: int, max_size: int):
        self.file_size = file_size
        self.max_size = max_size
        super().__init__(
            f"Document size {file_size} bytes exceeds maximum {max_size} bytes",
            details={"file_size": file_size, "max_size": max_size},
            error_code="DOCUMENT_TOO_LARGE",
        )


class UnsupportedDocumentFormatError(DocumentProcessingError):
    """Unsupported document format."""

    def __init__(self, file_type: str, supported_types: list):
        self.file_type = file_type
        self.supported_types = supported_types
        super().__init__(
            f"Unsupported document format: {file_type}",
            details={"file_type": file_type, "supported_types": supported_types},
            error_code="UNSUPPORTED_FORMAT",
        )


class DocumentCorruptedError(DocumentProcessingError):
    """Document is corrupted or unreadable."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(
            f"Document corrupted: {reason}",
            details={"reason": reason},
            error_code="DOCUMENT_CORRUPTED",
        )


class ExtractionValidationError(TenderExtractionException):
    """Extraction result validation errors."""

    def __init__(self, validation_errors: Dict[str, Any]):
        self.validation_errors = validation_errors
        super().__init__(
            "Extraction validation failed",
            details={"validation_errors": validation_errors},
            error_code="EXTRACTION_VALIDATION_FAILED",
        )


class JobNotFoundError(TenderExtractionException):
    """Job not found in the system."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(
            f"Job not found: {job_id}", details={"job_id": job_id}, error_code="JOB_NOT_FOUND"
        )


class ServiceUnavailableError(TenderExtractionException):
    """Service temporarily unavailable."""

    pass


# Generic LLM exceptions for multi-provider support
class LLMError(TenderExtractionException):
    """Generic LLM service error."""

    pass


class LLMRateLimitError(LLMError):
    """LLM service rate limit exceeded."""

    def __init__(self, provider: str = "LLM", retry_after: Optional[int] = None):
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(
            f"{provider} rate limit exceeded",
            details={"provider": provider, "retry_after": retry_after},
            error_code="LLM_RATE_LIMIT",
        )


class LLMQuotaExceededError(LLMError):
    """LLM service quota exceeded."""

    def __init__(self, provider: str = "LLM", quota_type: str = "monthly"):
        self.provider = provider
        self.quota_type = quota_type
        super().__init__(
            f"{provider} {quota_type} quota exceeded",
            details={"provider": provider, "quota_type": quota_type},
            error_code="LLM_QUOTA_EXCEEDED",
        )


# Provider-specific exceptions
class OllamaConnectionError(LLMError):
    """Ollama connection error."""

    def __init__(self, endpoint: str, reason: str):
        self.endpoint = endpoint
        self.reason = reason
        super().__init__(
            f"Ollama connection failed to {endpoint}: {reason}",
            details={"endpoint": endpoint, "reason": reason},
            error_code="OLLAMA_CONNECTION_ERROR",
        )


class OpenAIRateLimitError(LLMRateLimitError):
    """OpenAI-specific rate limit error."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__(provider="OpenAI", retry_after=retry_after)


class OpenAIConnectionError(LLMError):
    """OpenAI connection error."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(
            f"OpenAI connection failed: {reason}",
            details={"reason": reason},
            error_code="OPENAI_CONNECTION_ERROR",
        )


# Job processing exceptions
class JobExecutionTimeoutError(TenderExtractionException):
    """Job execution timed out."""

    def __init__(self, job_id: str, timeout_seconds: int):
        self.job_id = job_id
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Job {job_id} timed out after {timeout_seconds} seconds",
            details={"job_id": job_id, "timeout_seconds": timeout_seconds},
            error_code="JOB_EXECUTION_TIMEOUT",
        )


class BatchProcessingError(TenderExtractionException):
    """Batch processing error."""

    def __init__(self, batch_id: str, failed_documents: list, reason: str):
        self.batch_id = batch_id
        self.failed_documents = failed_documents
        self.reason = reason
        super().__init__(
            f"Batch processing failed for batch {batch_id}: {reason}",
            details={"batch_id": batch_id, "failed_documents": failed_documents, "reason": reason},
            error_code="BATCH_PROCESSING_ERROR",
        )


class DocumentValidationError(TenderExtractionException):
    """Document validation error with field-specific details."""

    def __init__(self, filename: str, field_errors: Dict[str, str]):
        self.filename = filename
        self.field_errors = field_errors
        super().__init__(
            f"Document validation failed for {filename}",
            details={"filename": filename, "field_errors": field_errors},
            error_code="DOCUMENT_VALIDATION_ERROR",
        )


# HTTP Exception mappings
def map_to_http_exception(exc: TenderExtractionException) -> HTTPException:
    """Map internal exceptions to HTTP exceptions."""

    error_mappings = {
        GeminiRateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
        GeminiQuotaExceededError: status.HTTP_503_SERVICE_UNAVAILABLE,
        DocumentTooLargeError: status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        UnsupportedDocumentFormatError: status.HTTP_400_BAD_REQUEST,
        DocumentCorruptedError: status.HTTP_400_BAD_REQUEST,
        ExtractionValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
        JobNotFoundError: status.HTTP_404_NOT_FOUND,
        ServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
        # Provider-specific exceptions
        OllamaConnectionError: status.HTTP_503_SERVICE_UNAVAILABLE,
        OpenAIRateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
        OpenAIConnectionError: status.HTTP_503_SERVICE_UNAVAILABLE,
        # Job processing exceptions
        JobExecutionTimeoutError: status.HTTP_408_REQUEST_TIMEOUT,
        BatchProcessingError: status.HTTP_422_UNPROCESSABLE_ENTITY,
        DocumentValidationError: status.HTTP_400_BAD_REQUEST,
    }

    status_code = error_mappings.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    headers = {}
    if isinstance(exc, GeminiRateLimitError) and exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)

    return HTTPException(
        status_code=status_code,
        detail={"message": exc.message, "error_code": exc.error_code, "details": exc.details},
        headers=headers if headers else None,
    )
