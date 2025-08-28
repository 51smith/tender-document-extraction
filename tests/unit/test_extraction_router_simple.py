"""Simplified tests for the extraction router endpoints using direct function calls."""

from io import BytesIO
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.extraction import (
    BatchExtractionRequest,
    DocumentExtractionRequest,
    ExtractionJob,
    ExtractionStatus,
)
from app.routers.extraction import (
    delete_job,
    export_job_results,
    extract_batch,
    get_extraction_statistics,
    get_job_status,
    list_jobs,
)


@pytest.fixture
def mock_job_manager():
    """Mock job manager fixture."""
    return AsyncMock()


@pytest.fixture
def sample_extraction_job():
    """Sample extraction job for testing."""
    from datetime import datetime

    job_id = str(uuid4())
    request = BatchExtractionRequest(
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
        request=request,
    )


@pytest.fixture
def completed_extraction_job():
    """Completed extraction job with results."""
    job_id = str(uuid4())
    result = {
        "project_title": "Test Project",
        "estimated_value": 100000.0,
        "submission_deadline": "2024-12-31T23:59:59Z",
    }
    from datetime import datetime

    request = BatchExtractionRequest(
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
        request=request,
        result=result,
    )


class TestBatchExtractionFunction:
    """Tests for the batch extraction function."""

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_extract_batch_success(self, mock_get_job_manager, mock_job_manager):
        """Test successful batch extraction request."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.create_extraction_job.return_value = job_id

        # Create mock upload files
        from fastapi import UploadFile

        mock_file = AsyncMock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.size = 1000
        mock_file.read.return_value = b"test content"

        files = [mock_file]

        # Execute
        with patch("app.config.settings.max_file_size", 10000):
            with patch("app.config.settings.batch_size_limit", 10):
                result = await extract_batch(
                    files=files,
                    config_name="default",
                    template_override=None,
                    enable_multimodal=True,
                    priority=0,
                    job_manager=mock_job_manager,
                )

        # Assert
        assert result["job_id"] == job_id
        assert result["status"] == "queued"
        assert "1 documents" in result["message"]

        # Verify job manager was called correctly
        mock_job_manager.create_extraction_job.assert_called_once()

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_extract_batch_size_limit(self, mock_get_job_manager, mock_job_manager):
        """Test batch extraction with size limit exceeded."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager

        from fastapi import UploadFile

        # Create multiple mock files
        files = []
        for i in range(5):
            mock_file = AsyncMock(spec=UploadFile)
            mock_file.filename = f"test{i}.pdf"
            mock_file.content_type = "application/pdf"
            mock_file.size = 1000
            files.append(mock_file)

        # Execute with low batch limit
        with patch("app.config.settings.batch_size_limit", 2):
            with pytest.raises(HTTPException) as exc_info:
                await extract_batch(
                    files=files,
                    config_name="default",
                    template_override=None,
                    enable_multimodal=True,
                    priority=0,
                    job_manager=mock_job_manager,
                )

        # Assert
        assert exc_info.value.status_code == 400
        assert "Batch size exceeds limit" in str(exc_info.value.detail)


class TestJobStatusFunction:
    """Tests for job status function."""

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_get_job_status_success(
        self, mock_get_job_manager, mock_job_manager, sample_extraction_job
    ):
        """Test successful job status retrieval."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.return_value = sample_extraction_job

        # Execute
        result = await get_job_status(sample_extraction_job.job_id, mock_job_manager)

        # Assert
        assert result.job_id == sample_extraction_job.job_id
        assert result.status == ExtractionStatus.PENDING
        mock_job_manager.get_job.assert_called_once_with(sample_extraction_job.job_id)

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, mock_get_job_manager, mock_job_manager):
        """Test job status for non-existent job."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.side_effect = HTTPException(
            status_code=404, detail="Job not found"
        )

        # Execute & Assert
        with pytest.raises(HTTPException):
            await get_job_status(job_id, mock_job_manager)


class TestJobDeletionFunction:
    """Tests for job deletion function."""

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_delete_job_cancel(self, mock_get_job_manager, mock_job_manager):
        """Test job cancellation (force=false)."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.cancel_job.return_value = True

        # Execute
        result = await delete_job(job_id, force=False, job_manager=mock_job_manager)

        # Assert
        assert "cancelled" in result["message"]
        mock_job_manager.cancel_job.assert_called_once_with(job_id)

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_delete_job_force(self, mock_get_job_manager, mock_job_manager):
        """Test job force deletion."""
        # Setup
        job_id = str(uuid4())
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.delete_job.return_value = True

        # Execute
        result = await delete_job(job_id, force=True, job_manager=mock_job_manager)

        # Assert
        assert "deleted permanently" in result["message"]
        mock_job_manager.delete_job.assert_called_once_with(job_id)


class TestJobListingFunction:
    """Tests for job listing function."""

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_list_jobs_default(
        self, mock_get_job_manager, mock_job_manager, sample_extraction_job
    ):
        """Test job listing with default parameters."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.list_jobs.return_value = [sample_extraction_job]

        # Execute
        result = await list_jobs(job_manager=mock_job_manager)

        # Assert
        assert len(result) == 1
        assert result[0].job_id == sample_extraction_job.job_id

        # Verify default parameters
        mock_job_manager.list_jobs.assert_called_once_with(limit=50, offset=0, status_filter=None)

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_list_jobs_with_parameters(self, mock_get_job_manager, mock_job_manager):
        """Test job listing with custom parameters."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.list_jobs.return_value = []

        # Execute
        result = await list_jobs(
            limit=10, offset=20, status=ExtractionStatus.COMPLETED, job_manager=mock_job_manager
        )

        # Assert
        assert result == []
        mock_job_manager.list_jobs.assert_called_once_with(
            limit=10, offset=20, status_filter=ExtractionStatus.COMPLETED
        )

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_list_jobs_limit_capped(self, mock_get_job_manager, mock_job_manager):
        """Test job listing with limit exceeding maximum."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.list_jobs.return_value = []

        # Execute
        result = await list_jobs(limit=200, job_manager=mock_job_manager)

        # Assert
        # Limit should be capped at 100
        mock_job_manager.list_jobs.assert_called_once_with(limit=100, offset=0, status_filter=None)


class TestJobExportFunction:
    """Tests for job export function."""

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_export_job_results_json(
        self, mock_get_job_manager, mock_job_manager, completed_extraction_job
    ):
        """Test exporting completed job results as JSON."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.return_value = completed_extraction_job

        # Execute
        result = await export_job_results(
            completed_extraction_job.job_id, format="json", job_manager=mock_job_manager
        )

        # Assert
        assert result.status_code == 200
        assert "attachment" in result.headers.get("content-disposition", "")

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_export_job_not_completed(
        self, mock_get_job_manager, mock_job_manager, sample_extraction_job
    ):
        """Test exporting job that is not completed."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.return_value = sample_extraction_job

        # Execute & Assert
        with pytest.raises(HTTPException) as exc_info:
            await export_job_results(
                sample_extraction_job.job_id, format="json", job_manager=mock_job_manager
            )

        assert exc_info.value.status_code == 400
        assert "not completed" in str(exc_info.value.detail)

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_export_job_unsupported_format(
        self, mock_get_job_manager, mock_job_manager, completed_extraction_job
    ):
        """Test exporting job with unsupported format."""
        # Setup
        mock_get_job_manager.return_value = mock_job_manager
        mock_job_manager.get_job.return_value = completed_extraction_job

        # Execute & Assert
        with pytest.raises(HTTPException) as exc_info:
            await export_job_results(
                completed_extraction_job.job_id, format="csv", job_manager=mock_job_manager
            )

        assert exc_info.value.status_code == 400
        assert "not supported" in str(exc_info.value.detail)


class TestStatisticsFunction:
    """Tests for statistics function."""

    @patch("app.routers.extraction.get_job_manager")
    @pytest.mark.asyncio
    async def test_get_extraction_statistics(self, mock_get_job_manager, mock_job_manager):
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
        result = await get_extraction_statistics(job_manager=mock_job_manager)

        # Assert
        assert result == expected_stats
        mock_job_manager.get_job_statistics.assert_called_once()
