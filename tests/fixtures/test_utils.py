"""
Test utilities and helper functions.
"""

import asyncio

from httpx import AsyncClient

from main import app


class TestAPIClient:
    """Enhanced API client for testing."""

    def __init__(self, client: AsyncClient):
        self.client = client
        self.base_url = "http://test"

    async def upload_file(
        self,
        file_content: bytes,
        filename: str = "test.pdf",
        content_type: str = "application/pdf",
        config_name: str = "default",
        enable_multimodal: bool = True,
        """Upload a file for extraction."""
        files = {"files": (filename, file_content, content_type)}
        data = {"config_name": config_name, "enable_multimodal": str(enable_multimodal).lower()}

        response = await self.client.post("/api/v1/extract/batch", files=files, data=data)
        return response.json(), response.status_code

        """Get job status."""
        response = await self.client.get(f"/api/v1/jobs/{job_id}")
        return response.json(), response.status_code

    async def wait_for_job_completion(
        self, job_id: str, timeout: int = 30, poll_interval: float = 0.5
        """Wait for job to complete."""
        start_time = asyncio.get_event_loop().time()

        while True:
            job_data, status_code = await self.get_job_status(job_id)

            if status_code != 200:
                raise Exception(f"Failed to get job status: {status_code}")

            status = job_data.get("status")
            if status in ["completed", "failed", "cancelled"]:
                return job_data

            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")

            await asyncio.sleep(poll_interval)

        """Check API health."""
        response = await self.client.get("/health")
        return response.json(), response.status_code

        """Get usage statistics."""
        response = await self.client.get("/api/v1/usage")
        return response.json(), response.status_code


def create_temp_pdf(content: str = "Test PDF Content") -> bytes:
    """Create a temporary PDF file for testing."""
    # Simple PDF structure for testing
    pdf_content = f"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Resources <<
  /Font <<
    /F1 4 0 R
  >>
>>
/Contents 5 0 R
>>
endobj

4 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj

5 0 obj
<<
/Length {len(content) + 50}
>>
stream
BT
/F1 12 Tf
100 700 Td
({content}) Tj
ET
endstream
endobj

xref
0 6
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
{400 + len(content)}
%%EOF"""

    return pdf_content.encode("utf-8")


def create_temp_text_file(content: str = "Test text content") -> bytes:
    """Create a temporary text file for testing."""
    return content.encode("utf-8")


def create_temp_docx_file() -> bytes:
    """Create a temporary DOCX file for testing."""
    # Minimal DOCX structure (ZIP-based)
    import io
    import zipfile

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Add minimal DOCX structure
        zip_file.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
</Types>""",
        )

        zip_file.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>""",
        )

        zip_file.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:r>
                <w:t>Test DOCX Content</w:t>
            </w:r>
        </w:p>
    </w:body>
</w:document>""",
        )

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


class MockAsyncContext:
    """Mock async context manager for testing."""

    def __init__(self, mock_obj):
        self.mock_obj = mock_obj

    async def __aenter__(self):
        return self.mock_obj

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def patch_async_context(target: str, mock_obj: Any):
    """Patch an async context manager."""
    return patch(target, return_value=MockAsyncContext(mock_obj))


    """Assert that an extraction result is valid."""
    assert "extracted_data" in result
    assert "confidence_scores" in result
    assert "processing_metadata" in result

    extracted_data = result["extracted_data"]
    confidence_scores = result["confidence_scores"]

    # Check required fields
    assert "project_title" in extracted_data
    assert extracted_data["project_title"] is not None

    if "contracting_authority" in extracted_data:
        assert "name" in extracted_data["contracting_authority"]

    if "estimated_value" in extracted_data:
        value = extracted_data["estimated_value"]
        if value:
            assert "amount" in value
            assert "currency" in value

    # Check confidence scores
    assert "overall" in confidence_scores
    assert confidence_scores["overall"] >= min_confidence

    # Check metadata
    metadata = result["processing_metadata"]
    assert "processing_time" in metadata
    assert metadata["processing_time"] > 0


    """Assert that job data is valid."""
    required_fields = ["job_id", "status", "created_at", "updated_at"]
    for field in required_fields:
        assert field in job_data, f"Missing required field: {field}"

    assert job_data["status"] in ["queued", "processing", "completed", "failed", "cancelled"]

    if job_data["status"] == "completed":
        assert "result" in job_data
        assert job_data["result"] is not None

    if job_data["status"] == "failed":
        assert "error_message" in job_data


    """Create multiple test files for batch processing."""
    files = []
    for i in range(count):
        content = create_temp_pdf(f"Test document {i+1}")
        filename = f"test_doc_{i+1}.pdf"
        files.append((filename, content, "application/pdf"))
    return files


async def simulate_concurrent_jobs(
    client: TestAPIClient, file_count: int = 3, concurrent_jobs: int = 2
    """Simulate concurrent job submissions."""
    job_ids = []

    # Submit jobs concurrently
    tasks = []
        files = create_batch_test_files(file_count)
        for filename, content, mime_type in files:
            task = client.upload_file(content, filename, mime_type)
            tasks.append(task)

    responses = await asyncio.gather(*tasks)

    for response, status_code in responses:
        if status_code == 200 and "job_id" in response:
            job_ids.append(response["job_id"])

    return job_ids


    """Create performance test scenarios."""
    return {
        "small_load": {
            "file_size": 1000,  # 1KB
            "file_count": 5,
            "concurrent_jobs": 2,
            "expected_time": 10.0,  # seconds
        },
        "medium_load": {
            "file_size": 10000,  # 10KB
            "file_count": 10,
            "concurrent_jobs": 5,
            "expected_time": 30.0,
        },
        "large_load": {
            "file_size": 100000,  # 100KB
            "file_count": 20,
            "concurrent_jobs": 10,
            "expected_time": 60.0,
        },
    }


class ErrorSimulator:
    """Utility to simulate various error conditions."""

    @staticmethod
    def create_network_error():
        """Create a network error."""
        import requests

        return requests.ConnectionError("Network unreachable")

    @staticmethod
    def create_timeout_error():
        """Create a timeout error."""
        import asyncio

        return asyncio.TimeoutError("Operation timed out")

    @staticmethod
    def create_api_quota_error():
        """Create an API quota error."""
        from app.core.exceptions import GeminiQuotaExceededError

        return GeminiQuotaExceededError("API quota exceeded")

    @staticmethod
    def create_rate_limit_error():
        """Create a rate limit error."""
        from app.core.exceptions import GeminiRateLimitError

        return GeminiRateLimitError("Rate limit exceeded")

    @staticmethod
    def create_model_error():
        """Create a model error."""
        from app.core.exceptions import GeminiModelError

        return GeminiModelError("Model processing failed")


def setup_test_environment():
    """Setup test environment with all necessary mocks."""
    with patch("app.services.gemini_service.genai") as mock_genai, patch(
        "app.services.job_manager.redis"
    ) as mock_redis, patch("app.utils.document_processor.PyPDF2") as mock_pypdf2, patch(
        "app.utils.document_processor.docx"
    ) as mock_docx:
        # Configure genai mock
        mock_genai.configure = MagicMock()
        mock_genai.GenerativeModel.return_value = MagicMock()

        # Configure Redis mock
        mock_redis.Redis.return_value = AsyncMock()

        # Configure PDF processor mock
        mock_pypdf2.PdfReader.return_value = MagicMock()

        # Configure DOCX processor mock
        mock_docx.Document.return_value = MagicMock()

        yield {"genai": mock_genai, "redis": mock_redis, "pypdf2": mock_pypdf2, "docx": mock_docx}


async def test_api_client():
    """Create test API client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield TestAPIClient(client)


def temp_file():
    """Create temporary file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        yield Path(tmp.name)
    Path(tmp.name).unlink(missing_ok=True)
