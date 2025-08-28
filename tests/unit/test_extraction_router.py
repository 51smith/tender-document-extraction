"""Tests for the extraction router endpoints."""

import json
from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from main import app
from app.models.extraction import (
    BatchExtractionRequest,
    ConfidenceScores,
    DocumentExtractionRequest,
    ExtractionJob,
    ExtractionNotes,
    ExtractionStatus,
    ProcessingMetadata,
    TenderExtractedData,
    TenderExtractionResult,
)


# Use the sync_client fixture from conftest.py


@pytest.fixture
def mock_job_manager():
    """Mock job manager fixture."""
    return AsyncMock()


@pytest.fixture
def sample_file():
    """Sample file for testing."""
    content = b"Sample PDF content for testing"
    return ("test.pdf", BytesIO(content), "application/pdf")


@pytest.fixture
def large_file():
    """Large file that exceeds size limits."""
    large_content = b"x" * (10 * 1024 * 1024)  # 10MB
    return ("large.pdf", BytesIO(large_content), "application/pdf")


@pytest.fixture
def sample_extraction_job():
    """Sample extraction job for testing."""
    job_id = str(uuid4())
    batch_request = BatchExtractionRequest(
        documents=[
            DocumentExtractionRequest(
                filename="test.pdf",
                content_type="application/pdf",
                config_name="default",
                enable_multimodal=True,
            )
        ],
        priority=0,
    )
    return ExtractionJob(
        job_id=job_id,
        status=ExtractionStatus.PENDING,
        created_at=datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
        request=batch_request,
    )


@pytest.fixture
def completed_extraction_job():
    """Completed extraction job with results."""
    job_id = str(uuid4())
    
    # Create proper TenderExtractionResult with all required fields
    extraction_result = TenderExtractionResult(
        extracted_data=TenderExtractedData(
            project_title="Test Project",
            estimated_value=100000.0,
            submission_deadline=datetime.fromisoformat("2024-12-31T23:59:59+00:00"),
            contracting_authority="Test Authority",
            project_description="Test project description",
            evaluation_criteria=[],
            submission_requirements="Standard requirements",
            contact_information="test@example.com"
        ),
        confidence_scores=ConfidenceScores(
            project_title=0.95,
            estimated_value=0.90,
            submission_deadline=0.85,
            contracting_authority=0.90,
            overall=0.90
        ),
        extraction_notes=ExtractionNotes(
            total_fields=8,
            extracted_fields=7,
            skipped_fields=[],
            warnings=[],
            processing_notes="Successfully extracted all key information"
        ),
        processing_metadata=ProcessingMetadata(
            processing_time=2.5,
            model="gemini-2.5-pro",
            actual_tokens=1250,
            timestamp=datetime.fromisoformat("2024-01-01T00:30:00+00:00")
        )
    )
    
    batch_request = BatchExtractionRequest(
        documents=[
            DocumentExtractionRequest(
                filename="test.pdf",
                content_type="application/pdf",
                config_name="default",
                enable_multimodal=True,
            )
        ],
        priority=0,
    )
    
    return ExtractionJob(
        job_id=job_id,
        status=ExtractionStatus.COMPLETED,
        created_at=datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
        completed_at=datetime.fromisoformat("2024-01-01T01:00:00+00:00"),
        request=batch_request,
        result=[extraction_result],  # Result should be a list for batch requests
    )


class TestBatchExtraction:
    """Tests for the batch extraction endpoint."""

    @patch("app.routers.extraction.get_job_manager")
    def test_batch_extraction_success(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test successful batch extraction request."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.create_extraction_job = AsyncMock(return_value=job_id)

        # Create test file
        files = {"files": ("test.pdf", BytesIO(b"test content"), "application/pdf")}
        data = {
            "config_name": "default",
            "enable_multimodal": "true",
            "priority": "0",
        }

        # Execute
        response = sync_client.post("/api/v1/extract/batch", files=files, data=data)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["job_id"] == job_id
        assert response_data["status"] == "queued"
        assert "documents" in response_data["message"]

        # Verify job manager was called correctly
        mock_job_manager.create_extraction_job.assert_called_once()
        call_args = mock_job_manager.create_extraction_job.call_args
        batch_request = call_args[0][0]
        assert isinstance(batch_request, BatchExtractionRequest)
        assert len(batch_request.documents) == 1
        assert batch_request.documents[0].filename == "test.pdf"

    @patch("app.routers.extraction.get_job_manager")
    def test_batch_extraction_multiple_files(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test batch extraction with multiple files."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.create_extraction_job.return_value = job_id

        # Create multiple test files
        files = [
            ("files", ("test1.pdf", BytesIO(b"test content 1"), "application/pdf")),
            ("files", ("test2.pdf", BytesIO(b"test content 2"), "application/pdf")),
        ]
        data = {"config_name": "default", "priority": "5"}

        # Execute
        response = sync_client.post("/api/v1/extract/batch", files=files, data=data)

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["job_id"] == job_id
        assert "2 documents" in response_data["message"]

        # Verify batch request structure
        call_args = mock_job_manager.create_extraction_job.call_args
        batch_request = call_args[0][0]
        assert len(batch_request.documents) == 2
        assert batch_request.priority == 5

    @patch("app.config.settings.batch_size_limit", 2)
    def test_batch_size_limit_exceeded(self, sync_client):
        """Test batch size limit validation."""
        # Create files exceeding the limit
        files = [
            ("files", ("test1.pdf", BytesIO(b"content1"), "application/pdf")),
            ("files", ("test2.pdf", BytesIO(b"content2"), "application/pdf")),
            ("files", ("test3.pdf", BytesIO(b"content3"), "application/pdf")),
        ]

        # Execute
        response = sync_client.post("/api/v1/extract/batch", files=files)

        # Assert
        assert response.status_code == 400
        assert "Batch size exceeds limit" in response.json()["detail"]

    @patch("app.config.settings.max_file_size", 1024)  # 1KB limit
    def test_file_size_limit_exceeded(self, sync_client):
        """Test file size limit validation."""
        # Create file exceeding size limit
        large_content = b"x" * 2048  # 2KB file
        files = {"files": ("large.pdf", BytesIO(large_content), "application/pdf")}

        # Execute
        response = sync_client.post("/api/v1/extract/batch", files=files)

        # Assert
        assert response.status_code == 400
        assert "too large" in response.json()["detail"]

    @patch("app.routers.extraction.get_job_manager")
    def test_batch_extraction_with_template_override(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test batch extraction with template override."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.create_extraction_job.return_value = job_id

        files = {"files": ("test.pdf", BytesIO(b"test content"), "application/pdf")}
        data = {
            "config_name": "custom",
            "template_override": "custom template",
            "enable_multimodal": "false",
        }

        # Execute
        response = sync_client.post("/api/v1/extract/batch", files=files, data=data)

        # Assert
        assert response.status_code == 200

        # Verify document request parameters
        call_args = mock_job_manager.create_extraction_job.call_args
        batch_request = call_args[0][0]
        doc_request = batch_request.documents[0]
        assert doc_request.config_name == "custom"
        assert doc_request.template_override == "custom template"
        assert doc_request.enable_multimodal is False

    def test_batch_extraction_no_files(self, sync_client):
        """Test batch extraction with no files."""
        response = sync_client.post("/api/v1/extract/batch", files={})
        assert response.status_code == 422  # Validation error

    @patch("app.routers.extraction.get_job_manager")
    def test_batch_extraction_job_manager_error(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test batch extraction when job manager fails."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.create_extraction_job.side_effect = Exception("Job creation failed")

        files = {"files": ("test.pdf", BytesIO(b"test content"), "application/pdf")}

        # Execute
        response = sync_client.post("/api/v1/extract/batch", files=files)

        # Assert
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]


class TestJobStatus:
    """Tests for job status endpoint."""

    def test_get_job_status_success(self, sync_client, mock_job_manager, sample_extraction_job):
        """Test successful job status retrieval."""
        # Setup - Override the dependency
        from app.services.job_manager import get_job_manager
        
        def mock_get_job_manager_override():
            return mock_job_manager
        
        app.dependency_overrides[get_job_manager] = mock_get_job_manager_override
        mock_job_manager.get_job = AsyncMock(return_value=sample_extraction_job)
        
        try:
            # Execute
            response = sync_client.get(f"/api/v1/jobs/{sample_extraction_job.job_id}")

            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["job_id"] == sample_extraction_job.job_id
            assert response_data["status"] == "pending"
        finally:
            # Cleanup - remove the override
            if get_job_manager in app.dependency_overrides:
                del app.dependency_overrides[get_job_manager]

    def test_get_job_status_not_found(self, sync_client, mock_job_manager):
        """Test job status for non-existent job."""
        from app.core.exceptions import JobNotFoundError
        from app.services.job_manager import get_job_manager
        
        # Setup - Override the dependency
        def mock_get_job_manager_override():
            return mock_job_manager
        
        job_id = str(uuid4())
        app.dependency_overrides[get_job_manager] = mock_get_job_manager_override
        mock_job_manager.get_job = AsyncMock(side_effect=JobNotFoundError(job_id))
        
        try:
            # Execute
            response = sync_client.get(f"/api/v1/jobs/{job_id}")

            # Assert
            assert response.status_code == 404
        finally:
            # Cleanup - remove the override
            if get_job_manager in app.dependency_overrides:
                del app.dependency_overrides[get_job_manager]

    @patch("app.routers.extraction.get_job_manager")
    def test_get_job_status_server_error(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test job status endpoint with server error."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.side_effect = Exception("Database error")

        # Execute
        response = sync_client.get(f"/api/v1/jobs/{job_id}")

        # Assert
        assert response.status_code == 500


class TestJobDeletion:
    """Tests for job deletion endpoint."""

    @patch("app.routers.extraction.get_job_manager")
    def test_delete_job_cancel(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test job cancellation (force=false)."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.cancel_job.return_value = True

        # Execute
        response = sync_client.delete(f"/api/v1/jobs/{job_id}")

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert "cancelled" in response_data["message"]
        mock_job_manager.cancel_job.assert_called_once_with(job_id)

    @patch("app.routers.extraction.get_job_manager")
    def test_delete_job_force(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test job force deletion."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.delete_job.return_value = True

        # Execute
        response = sync_client.delete(f"/api/v1/jobs/{job_id}?force=true")

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert "deleted permanently" in response_data["message"]
        mock_job_manager.delete_job.assert_called_once_with(job_id)

    @patch("app.routers.extraction.get_job_manager")
    def test_delete_job_not_found(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test deleting non-existent job with force=true."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.delete_job.return_value = False

        # Execute
        response = sync_client.delete(f"/api/v1/jobs/{job_id}?force=true")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("app.routers.extraction.get_job_manager")
    def test_delete_job_cannot_cancel(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test cancelling job that cannot be cancelled."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.cancel_job.return_value = False

        # Execute
        response = sync_client.delete(f"/api/v1/jobs/{job_id}")

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert "cannot be cancelled" in response_data["message"]


class TestJobListing:
    """Tests for job listing endpoint."""

    @patch("app.routers.extraction.get_job_manager")
    def test_list_jobs_default(self, mock_get_job_manager, sync_client, mock_job_manager, sample_extraction_job):
        """Test job listing with default parameters."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.list_jobs.return_value = [sample_extraction_job]

        # Execute
        response = sync_client.get("/api/v1/jobs")

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 1
        assert response_data[0]["job_id"] == sample_extraction_job.job_id

        # Verify default parameters
        mock_job_manager.list_jobs.assert_called_once_with(limit=50, offset=0, status_filter=None)

    @patch("app.routers.extraction.get_job_manager")
    def test_list_jobs_with_parameters(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test job listing with custom parameters."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.list_jobs.return_value = []

        # Execute
        response = sync_client.get("/api/v1/jobs?limit=10&offset=20&status=completed")

        # Assert
        assert response.status_code == 200
        mock_job_manager.list_jobs.assert_called_once_with(
            limit=10, offset=20, status_filter=ExtractionStatus.COMPLETED
        )

    @patch("app.routers.extraction.get_job_manager")
    def test_list_jobs_limit_capped(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test job listing with limit exceeding maximum."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.list_jobs.return_value = []

        # Execute
        response = sync_client.get("/api/v1/jobs?limit=200")

        # Assert
        assert response.status_code == 200
        # Limit should be capped at 100
        mock_job_manager.list_jobs.assert_called_once_with(limit=100, offset=0, status_filter=None)

    @patch("app.routers.extraction.get_job_manager")
    def test_list_jobs_server_error(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test job listing with server error."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.list_jobs.side_effect = Exception("Database error")

        # Execute
        response = sync_client.get("/api/v1/jobs")

        # Assert
        assert response.status_code == 500


class TestJobExport:
    """Tests for job export endpoint."""

    @patch("app.routers.extraction.get_job_manager")
    def test_export_job_results_json(self, mock_get_job_manager, sync_client, mock_job_manager, completed_extraction_job):
        """Test exporting completed job results as JSON."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.return_value = completed_extraction_job

        # Execute
        response = sync_client.get(f"/api/v1/jobs/{completed_extraction_job.job_id}/export")

        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers.get("content-disposition", "")

        # Verify content
        response_data = response.json()
        assert "project_title" in response_data
        assert response_data["project_title"] == "Test Project"

    @patch("app.routers.extraction.get_job_manager")
    def test_export_job_not_completed(self, mock_get_job_manager, sync_client, mock_job_manager, sample_extraction_job):
        """Test exporting job that is not completed."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.return_value = sample_extraction_job

        # Execute
        response = sync_client.get(f"/api/v1/jobs/{sample_extraction_job.job_id}/export")

        # Assert
        assert response.status_code == 400
        assert "not completed" in response.json()["detail"]

    @patch("app.routers.extraction.get_job_manager")
    def test_export_job_no_results(self, mock_get_job_manager, sync_client, mock_job_manager, completed_extraction_job):
        """Test exporting completed job with no results."""
        # Setup - completed job but no results
        completed_extraction_job.result = None
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.return_value = completed_extraction_job

        # Execute
        response = sync_client.get(f"/api/v1/jobs/{completed_extraction_job.job_id}/export")

        # Assert
        assert response.status_code == 404
        assert "No results found" in response.json()["detail"]

    @patch("app.routers.extraction.get_job_manager")
    def test_export_job_unsupported_format(self, mock_get_job_manager, sync_client, mock_job_manager, completed_extraction_job):
        """Test exporting job with unsupported format."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.return_value = completed_extraction_job

        # Execute
        response = sync_client.get(f"/api/v1/jobs/{completed_extraction_job.job_id}/export?format=csv")

        # Assert
        assert response.status_code == 400
        assert "not supported" in response.json()["detail"]

    @patch("app.routers.extraction.get_job_manager")
    def test_export_job_not_found(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test exporting non-existent job."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.side_effect = HTTPException(status_code=404, detail="Job not found")

        # Execute
        response = sync_client.get(f"/api/v1/jobs/{job_id}/export")

        # Assert
        assert response.status_code == 404


class TestStatistics:
    """Tests for statistics endpoint."""

    @patch("app.routers.extraction.get_job_manager")
    def test_get_extraction_statistics(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test getting extraction statistics."""
        # Setup
        expected_stats = {
            "total_jobs": 100,
            "completed_jobs": 80,
            "failed_jobs": 5,
            "pending_jobs": 15,
            "average_processing_time": 45.2,
        }
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job_statistics.return_value = expected_stats

        # Execute
        response = sync_client.get("/api/v1/statistics")

        # Assert
        assert response.status_code == 200
        response_data = response.json()
        assert response_data == expected_stats

    @patch("app.routers.extraction.get_job_manager")
    def test_get_extraction_statistics_error(self, mock_get_job_manager, sync_client, mock_job_manager):
        """Test getting statistics with server error."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job_statistics.side_effect = Exception("Statistics error")

        # Execute
        response = sync_client.get("/api/v1/statistics")

        # Assert
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]