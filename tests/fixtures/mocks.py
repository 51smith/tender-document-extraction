"""
Comprehensive mock utilities and fixtures for testing.
"""

import asyncio
import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.core.exceptions import (
    ExtractionValidationError,
    GeminiAPIException,
    GeminiModelError,
    GeminiQuotaExceededError,
    GeminiRateLimitError,
    JobNotFoundError,
    LLMError,
)
from app.models.extraction import (
    ConfidenceScores,
    ContractingAuthority,
    ContractType,
    EstimatedValue,
    EvaluationCriterion,
    ExtractionNotes,
    ProcessingMetadata,
    TenderExtractedData,
    TenderExtractionResult,
)
from app.models.extraction import ExtractionStatus


class MockLLMService:
    """Mock LLM service with configurable responses and error simulation."""

    def __init__(self, provider: str = "gemini", model: str = "gemini-2.5-pro"):
        self.provider = provider
        self.model = model
        self.call_count = 0
        self.responses = []
        self.errors = []
        self.latency = 1.0
        
    def add_response(self, response: Dict[str, Any]) -> None:
        """Add a response to the queue."""
        self.responses.append(response)
        
    def add_error(self, error: Exception) -> None:
        """Add an error to the queue."""
        self.errors.append(error)
        
    def set_latency(self, seconds: float) -> None:
        """Set response latency."""
        self.latency = seconds
        
    async def generate_content(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Mock generate_content method."""
        import asyncio
        await asyncio.sleep(self.latency)
        
        self.call_count += 1
        
        # Simulate errors first
        if self.errors:
            error = self.errors.pop(0)
            raise error
            
        # Return queued responses
        if self.responses:
            return self.responses.pop(0)
            
        # Default response
        return self._default_response()
        
    async def health_check(self) -> bool:
        """Mock health check."""
        if self.errors and isinstance(self.errors[0], (GeminiAPIException, LLMError)):
            return False
        return True
        
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self.provider
        
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider info."""
        return {
            "provider": self.provider,
            "model": self.model,
            "capabilities": ["text", "multimodal"]
        }
        
    def _default_response(self) -> Dict[str, Any]:
        """Generate a default response."""
        return {
            "response": json.dumps({
                "extracted_data": {
                    "project_title": "Test Project",
                    "contracting_authority": {"name": "Test Authority"},
                    "estimated_value": {"amount": 100000, "currency": "EUR"},
                    "contract_type": "works"
                },
                "confidence_scores": {
                    "project_title": 0.9,
                    "contracting_authority": 0.85,
                    "estimated_value": 0.8,
                    "overall": 0.85
                },
                "extraction_notes": {
                    "ambiguities": [],
                    "assumptions": [],
                    "missing_information": [],
                    "recommendations": []
                }
            }),
            "usage": {"total_token_count": 1200}
        }


class MockRedisClient:
    """Mock Redis client for job queue testing."""
    
    def __init__(self):
        self.data = {}
        self.lists = {}
        self.sorted_sets = {}
        self.connected = True
        
    async def ping(self) -> bool:
        """Mock ping."""
        return self.connected
        
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Mock set."""
        self.data[key] = value
        return True
        
    async def get(self, key: str) -> Optional[str]:
        """Mock get."""
        return self.data.get(key)
        
    async def hset(self, name: str, key: str, value: str) -> int:
        """Mock hset."""
        if name not in self.data:
            self.data[name] = {}
        self.data[name][key] = value
        return 1
        
    async def hgetall(self, name: str) -> Dict[str, str]:
        """Mock hgetall."""
        return self.data.get(name, {})
        
    async def lpush(self, key: str, *values: str) -> int:
        """Mock lpush."""
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key].extend(reversed(values))
        return len(self.lists[key])
        
    async def brpop(self, keys: List[str], timeout: int = 0) -> Optional[tuple]:
        """Mock brpop."""
        for key in keys:
            if key in self.lists and self.lists[key]:
                value = self.lists[key].pop()
                return (key, value)
        return None
        
    async def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        """Mock zadd."""
        if key not in self.sorted_sets:
            self.sorted_sets[key] = {}
        self.sorted_sets[key].update(mapping)
        return len(mapping)
        
    async def zrange(self, key: str, start: int, end: int, withscores: bool = False) -> List:
        """Mock zrange."""
        if key not in self.sorted_sets:
            return []
        items = sorted(self.sorted_sets[key].items(), key=lambda x: x[1])
        if withscores:
            return items[start:end+1] if end != -1 else items[start:]
        return [item[0] for item in items[start:end+1]] if end != -1 else [item[0] for item in items[start:]]


class MockExtractionWorker:
    """Mock extraction worker for testing."""
    
    def __init__(self):
        self.processed_jobs = []
        self.processing_time = 2.0
        self.should_fail = False
        self.failure_message = "Mock extraction failed"
        
    async def process_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock job processing."""
        import asyncio
        await asyncio.sleep(self.processing_time)
        
        self.processed_jobs.append((job_id, job_data))
        
        if self.should_fail:
            raise ExtractionValidationError({"error": self.failure_message})
            
        return {
            "job_id": job_id,
            "status": "completed",
            "result": [self._mock_extraction_result()],
            "processing_time": self.processing_time
        }
        
    def set_processing_time(self, seconds: float) -> None:
        """Set processing time."""
        self.processing_time = seconds
        
    def set_failure(self, should_fail: bool, message: str = "Mock extraction failed") -> None:
        """Configure failure behavior."""
        self.should_fail = should_fail
        self.failure_message = message
        
    def _mock_extraction_result(self) -> Dict[str, Any]:
        """Generate mock extraction result."""
        return {
            "extracted_data": {
                "project_title": "Mock Project",
                "contracting_authority": {"name": "Mock Authority"},
                "estimated_value": {"amount": 500000, "currency": "EUR"}
            },
            "confidence_scores": {
                "project_title": 0.9,
                "contracting_authority": 0.85,
                "estimated_value": 0.8,
                "overall": 0.85
            },
            "processing_metadata": {
                "processing_time": self.processing_time,
                "model": "mock-model"
            },
            "extraction_notes": {
                "ambiguities": [],
                "assumptions": ["Mock assumption"],
                "missing_information": [],
                "recommendations": ["Mock recommendation"]
            }
        }


class MockJobManager:
    """Mock job manager for testing."""
    
    def __init__(self):
        self.jobs = {}
        self.job_queue = []
        self.processing = False
        
    async def submit_job(self, job_type: str, files: List[bytes], config: Dict[str, Any]) -> str:
        """Mock job submission."""
        job_id = str(uuid4())
        job_data = {
            "job_id": job_id,
            "job_type": job_type,
            "status": ExtractionStatus.PENDING,
            "files_count": len(files),
            "config": config,
            "created_at": time.time(),
            "updated_at": time.time(),
            "progress": 0.0
        }
        self.jobs[job_id] = job_data
        self.job_queue.append(job_id)
        return job_id
        
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Mock get job status."""
        if job_id not in self.jobs:
            raise JobNotFoundError(f"Job {job_id} not found")
        return self.jobs[job_id]
        
    async def get_job_result(self, job_id: str) -> Dict[str, Any]:
        """Mock get job result."""
        job_data = await self.get_job_status(job_id)
        if job_data["status"] != ExtractionStatus.COMPLETED:
            return {"status": job_data["status"], "result": None}
        return {
            "status": job_data["status"],
            "result": job_data.get("result", [])
        }
        
    async def cancel_job(self, job_id: str) -> bool:
        """Mock cancel job."""
        if job_id not in self.jobs:
            return False
        self.jobs[job_id]["status"] = ExtractionStatus.CANCELLED
        return True
        
    async def start_processing(self) -> None:
        """Mock start processing."""
        self.processing = True
        # Simulate processing jobs
        while self.job_queue and self.processing:
            job_id = self.job_queue.pop(0)
            self.jobs[job_id]["status"] = ExtractionStatus.PROCESSING
            self.jobs[job_id]["progress"] = 50.0
            # Simulate completion
            await asyncio.sleep(0.1)
            self.jobs[job_id]["status"] = ExtractionStatus.COMPLETED
            self.jobs[job_id]["progress"] = 100.0
            self.jobs[job_id]["result"] = [MockExtractionWorker()._mock_extraction_result()]
            
    async def stop_processing(self) -> None:
        """Mock stop processing."""
        self.processing = False
        
    def get_queue_size(self) -> int:
        """Get queue size."""
        return len(self.job_queue)


class MockDocumentProcessor:
    """Mock document processor for testing."""
    
    def __init__(self):
        self.processed_documents = []
        self.should_fail = False
        self.failure_message = "Mock processing failed"
        
    def process_document(self, content: bytes, filename: str, mime_type: Optional[str] = None):
        """Mock document processing."""
        from app.utils.document_processor import DocumentContent
        
        self.processed_documents.append((content, filename, mime_type))
        
        if self.should_fail:
            from app.core.exceptions import DocumentCorruptedError
            raise DocumentCorruptedError(self.failure_message)
            
        # Mock successful processing
        text_content = f"Mock processed content from {filename}"
        if content:
            text_content += f" ({len(content)} bytes)"
            
        return DocumentContent(
            text=text_content,
            images=[],
            tables=[],
            metadata={
                "filename": filename,
                "mime_type": mime_type or "application/octet-stream",
                "page_count": 1,
                "word_count": len(text_content.split())
            },
            content_hash=f"mock_hash_{hash(content)}",
            file_type=mime_type or "application/octet-stream",
            file_size=len(content) if content else 0
        )
        
    def set_failure(self, should_fail: bool, message: str = "Mock processing failed") -> None:
        """Configure failure behavior."""
        self.should_fail = should_fail
        self.failure_message = message
        
    def get_multimodal_content(self, document_content) -> List:
        """Mock multimodal content preparation."""
        return [document_content.text]
        
    def validate_document(self, document_content) -> Dict[str, Any]:
        """Mock document validation."""
        return {
            "is_valid": not self.should_fail,
            "errors": [self.failure_message] if self.should_fail else [],
            "warnings": []
        }


def create_mock_extraction_result(
    project_title: str = "Test Project",
    authority_name: str = "Test Authority", 
    value_amount: float = 100000.0,
    value_currency: str = "EUR",
    confidence_overall: float = 0.85
) -> TenderExtractionResult:
    """Create a mock extraction result with customizable fields."""
    return TenderExtractionResult(
        extracted_data=TenderExtractedData(
            project_title=project_title,
            contracting_authority=ContractingAuthority(name=authority_name),
            estimated_value=EstimatedValue(amount=Decimal(str(value_amount)), currency=value_currency),
            contract_type=ContractType.WORKS,
            evaluation_criteria=[
                EvaluationCriterion(criterion="Price", weight_percentage=Decimal("40")),
                EvaluationCriterion(criterion="Quality", weight_percentage=Decimal("60")),
            ]
        ),
        confidence_scores=ConfidenceScores(
            project_title=0.9,
            contracting_authority=0.85,
            estimated_value=0.8,
            overall=confidence_overall
        ),
        extraction_notes=ExtractionNotes(
            ambiguities=["Mock ambiguity"],
            assumptions=["Mock assumption"],
            missing_information=["Mock missing info"],
            recommendations=["Mock recommendation"]
        ),
        processing_metadata=ProcessingMetadata(
            processing_time=2.0,
            model="mock-model",
            estimated_tokens=1200,
            actual_tokens=1150
        )
    )


def create_mock_error_scenarios() -> Dict[str, Exception]:
    """Create various error scenarios for testing."""
    return {
        "rate_limit": GeminiRateLimitError(60),
        "quota_exceeded": GeminiQuotaExceededError("monthly"), 
        "api_error": GeminiAPIException("API connection failed"),
        "model_error": GeminiModelError("Model processing error", "gemini-2.5-pro"),
        "llm_service_error": LLMError("LLM service unavailable"),
        "extraction_error": ExtractionValidationError({"error": "Extraction failed"}),
        "job_not_found": JobNotFoundError("test-job-123")
    }


def create_performance_test_data() -> Dict[str, Any]:
    """Create data for performance testing."""
    return {
        "small_doc": b"A" * 1000,  # 1KB
        "medium_doc": b"B" * 10000,  # 10KB  
        "large_doc": b"C" * 100000,  # 100KB
        "batch_docs": [f"Doc{i}".encode() * 1000 for i in range(10)],
        "concurrent_jobs": 5,
        "stress_jobs": 50
    }


class MockUsageTracker:
    """Mock usage tracker for testing."""
    
    def __init__(self):
        self.requests_count = 0
        self.tokens_count = 0
        self.cost_usd = 0.0
        self.error_count = 0
        
    def track_request(self, tokens: int, cost: float) -> None:
        """Track a request."""
        self.requests_count += 1
        self.tokens_count += tokens
        self.cost_usd += cost
        
    def track_error(self) -> None:
        """Track an error."""
        self.error_count += 1
        
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "requests": self.requests_count,
            "tokens": self.tokens_count,
            "cost_usd": self.cost_usd,
            "errors": self.error_count,
            "success_rate": (self.requests_count - self.error_count) / max(self.requests_count, 1)
        }
        
    def reset_stats(self) -> None:
        """Reset statistics."""
        self.requests_count = 0
        self.tokens_count = 0
        self.cost_usd = 0.0
        self.error_count = 0