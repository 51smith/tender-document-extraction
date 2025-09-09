"""
Comprehensive tests for the JobManager service.
Testing coverage target: 19% → 85%
"""

import asyncio
import base64
import json
import time
import uuid
from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import JobNotFoundError, ServiceUnavailableError
from app.models.extraction import (
    BatchExtractionRequest,
    DocumentExtractionRequest,
    ExtractionJob,
    ExtractionStatus,
    TenderExtractionResult,
)
from app.services.job_manager import (
    JobManager,
    JobWorkerManager,
    cleanup_job_manager,
    get_job_manager,
    initialize_job_manager,
)


class TestJobManager:
    """Test JobManager class functionality."""

    @pytest.fixture()
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis async client."""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_client.set.return_value = True
        mock_client.get.return_value = None
        mock_client.expire.return_value = True
        mock_client.zadd.return_value = 1
        mock_client.zrevrange.return_value = []
        mock_client.zrem.return_value = 1
        mock_client.delete.return_value = 1
        mock_client.close.return_value = None
        mock_client.zcard.return_value = 10
        mock_client.zcount.return_value = 5
        mock_client.zrangebyscore.return_value = []
        mock_client.hgetall.return_value = {}
        mock_client.hget.return_value = None
        mock_client.hincrby.return_value = 1
        mock_client.hincrbyfloat.return_value = 1.0
        mock_client.keys.return_value = []
        mock_client.pipeline.return_value = AsyncMock()
        return mock_client

    @pytest.fixture()
    @pytest.fixture
    def mock_redis_connection_pool(self):
        """Mock Redis connection pool."""
        mock_pool = MagicMock()
        mock_pool.disconnect.return_value = asyncio.Future()
        mock_pool.disconnect.return_value.set_result(None)
        return mock_pool

    @pytest.fixture()
    @pytest.fixture
    def sample_document_request(self):
        """Create sample document extraction request."""
        return DocumentExtractionRequest(
            filename="test.pdf", content_type="application/pdf", config_name="default"
        )

    @pytest.fixture()
    @pytest.fixture
    def sample_batch_request(self):
        """Create sample batch extraction request."""
        return BatchExtractionRequest(
            documents=[
                DocumentExtractionRequest(filename="doc1.pdf", config_name="default"),
                DocumentExtractionRequest(filename="doc2.pdf", config_name="default"),
            ]
        )

    @pytest.fixture()
    @pytest.fixture
    def sample_extraction_job(self):
        """Create sample extraction job."""
        return ExtractionJob(
            job_id="test-job-123",
            status=ExtractionStatus.PENDING,
            created_at=datetime.now(UTC),
            created_at=datetime.now(timezone.utc),
            request=DocumentExtractionRequest(filename="test.pdf", config_name="default"),
            progress=0.0,
        )

    def test_job_manager_initialization(self):
        """Test JobManager initialization."""
        job_manager = JobManager()

        assert job_manager.redis_url is not None
        assert job_manager.max_concurrent_jobs > 0
        assert job_manager._redis_client is None
        assert job_manager._connection is None

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_redis_client, mock_redis_connection_pool):
        """Test successful Redis initialization."""
        job_manager = JobManager()

        with patch("redis.asyncio.ConnectionPool.from_url") as mock_pool_from_url, patch(
            "redis.asyncio.Redis"
        ) as mock_redis_class:
            mock_pool_from_url.return_value = mock_redis_connection_pool
            mock_redis_class.return_value = mock_redis_client

            await job_manager.initialize()

            assert job_manager._redis_client is not None
            assert job_manager._connection is not None
            mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self):
        """Test Redis initialization failure."""
        job_manager = JobManager()

        with patch("redis.asyncio.ConnectionPool.from_url") as mock_pool_from_url:
            mock_pool_from_url.side_effect = Exception("Connection failed")

            with pytest.raises(ServiceUnavailableError) as exc_info:
                await job_manager.initialize()

            assert "Job queue unavailable" in str(exc_info.value)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_cleanup(self, mock_redis_client, mock_redis_connection_pool):
        """Test cleanup of Redis connections."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client
        job_manager._connection = mock_redis_connection_pool

        await job_manager.cleanup()

        mock_redis_client.close.assert_called_once()
        mock_redis_connection_pool.disconnect.assert_called_once()

    def test_get_sync_connection(self):
        """Test getting synchronous Redis connection."""
        job_manager = JobManager()

        # The global mock_rq_infrastructure fixture already mocks _get_sync_connection
        # Just verify it returns a connection-like object
        sync_conn = job_manager._get_sync_connection()
        assert sync_conn is not None

    @pytest.mark.asyncio()
        with patch("rq.Connection") as mock_connection, patch(
            "redis.from_url"
        ) as mock_redis_from_url:
            mock_redis_from_url.return_value = MagicMock()

            sync_conn = job_manager._get_sync_connection()

            mock_connection.assert_called_once()
            mock_redis_from_url.assert_called_once_with(job_manager.redis_url)

    @pytest.mark.asyncio
    async def test_create_extraction_job_single_document(
        self, mock_redis_client, sample_document_request
    ):
        """Test creating a single document extraction job."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        file_contents = {"test.pdf": b"test content"}

        with patch.object(job_manager, "_enqueue_job") as mock_enqueue:
            job_id = await job_manager.create_extraction_job(
                sample_document_request, priority=5, file_contents=file_contents
            )

            # Verify job_id is valid UUID
            uuid.UUID(job_id)

            # Verify Redis operations
            mock_redis_client.set.assert_called()
            mock_redis_client.expire.assert_called()
            mock_redis_client.zadd.assert_called()

            # Verify job was enqueued
            mock_enqueue.assert_called_once_with(job_id, sample_document_request, 5)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_create_extraction_job_batch(self, mock_redis_client, sample_batch_request):
        """Test creating a batch extraction job."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        with patch.object(job_manager, "_enqueue_job") as mock_enqueue:
            job_id = await job_manager.create_extraction_job(sample_batch_request)

            # Verify job_id is valid UUID
            uuid.UUID(job_id)

            # Verify job was enqueued
            mock_enqueue.assert_called_once_with(job_id, sample_batch_request, 0)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_store_job(self, mock_redis_client, sample_extraction_job):
        """Test storing job in Redis."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        await job_manager._store_job(sample_extraction_job)

        # Verify Redis set call with job key
        mock_redis_client.set.assert_called()
        args, kwargs = mock_redis_client.set.call_args
        assert args[0] == f"job:{sample_extraction_job.job_id}"

        # Verify expire call
        mock_redis_client.expire.assert_called_with(
            f"job:{sample_extraction_job.job_id}", 86400 * 7
        )

        # Verify index update
        mock_redis_client.zadd.assert_called()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_store_file_contents(self, mock_redis_client):
        """Test storing file contents in Redis."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        job_id = "test-job-123"
        file_contents = {"doc1.pdf": b"content 1", "doc2.txt": b"content 2"}

        await job_manager._store_file_contents(job_id, file_contents)

        # Verify Redis operations
        mock_redis_client.set.assert_called()
        mock_redis_client.expire.assert_called_with(f"job:{job_id}:files", 86400 * 7)

        # Verify the stored data is base64 encoded
        args, kwargs = mock_redis_client.set.call_args
        stored_data = json.loads(args[1])
        assert base64.b64decode(stored_data["doc1.pdf"]) == b"content 1"
        assert base64.b64decode(stored_data["doc2.txt"]) == b"content 2"

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_get_file_contents_success(self, mock_redis_client):
        """Test retrieving file contents from Redis."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        job_id = "test-job-123"

        # Mock stored data (base64 encoded)
        stored_data = {
            "doc1.pdf": base64.b64encode(b"content 1").decode("utf-8"),
            "doc2.txt": base64.b64encode(b"content 2").decode("utf-8"),
        }
        mock_redis_client.get.return_value = json.dumps(stored_data)

        file_contents = await job_manager.get_file_contents(job_id)

        assert file_contents["doc1.pdf"] == b"content 1"
        assert file_contents["doc2.txt"] == b"content 2"
        mock_redis_client.get.assert_called_with(f"job:{job_id}:files")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_get_file_contents_not_found(self, mock_redis_client):
        """Test retrieving file contents when none exist."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.get.return_value = None

        file_contents = await job_manager.get_file_contents("nonexistent-job")

        assert file_contents == {}

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_enqueue_job_default_queue(self, mock_redis_client, sample_document_request):
        """Test enqueueing job to default queue."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_rq_job = MagicMock()
        mock_rq_job.id = "rq-job-123"

        with patch("app.services.job_manager.Queue") as mock_queue_class, patch.object(
        with patch("rq.Queue") as mock_queue_class, patch.object(
            job_manager, "_get_sync_connection"
        ) as mock_sync_conn, patch("asyncio.create_task") as mock_create_task:
            # Setup RQ mocks with proper connection context
            mock_queue = MagicMock()
            mock_queue.enqueue.return_value = mock_rq_job
            mock_queue_class.return_value = mock_queue

            # Setup context manager for sync connection
            mock_context = MagicMock()
            mock_context.__enter__ = lambda x: None
            mock_context.__exit__ = lambda x, y, z, w: None
            mock_sync_conn.return_value = mock_context

            await job_manager._enqueue_job("test-job-123", sample_document_request, priority=3)

            # Verify default queue was used (priority <= 5)
            mock_queue_class.assert_called_with("default")
            mock_queue.enqueue.assert_called_once()

            # Verify RQ job ID was stored
            mock_redis_client.set.assert_called_with("job:test-job-123:rq_id", "rq-job-123")

            # Verify fallback monitoring was started
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_enqueue_job_high_priority_queue(
        self, mock_redis_client, sample_document_request
    ):
        """Test enqueueing job to high priority queue."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_rq_job = MagicMock()
        mock_rq_job.id = "rq-job-123"

        with patch("app.services.job_manager.Queue") as mock_queue_class, patch.object(
            job_manager, "_get_sync_connection"
        ) as mock_sync_conn, patch("asyncio.create_task"):
        with patch("rq.Queue") as mock_queue_class, patch.object(
            job_manager, "_get_sync_connection"
        ) as mock_sync_conn, patch("asyncio.create_task") as mock_create_task:
            mock_queue = MagicMock()
            mock_queue.enqueue.return_value = mock_rq_job
            mock_queue_class.return_value = mock_queue

            # Setup context manager for sync connection
            mock_context = MagicMock()
            mock_context.__enter__ = lambda x: None
            mock_context.__exit__ = lambda x, y, z, w: None
            mock_sync_conn.return_value = mock_context

            await job_manager._enqueue_job("test-job-123", sample_document_request, priority=8)

            # Verify high priority queue was used (priority > 5)
            mock_queue_class.assert_called_with("high")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_get_job_success(self, mock_redis_client, sample_extraction_job):
        """Test retrieving existing job."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Mock stored job data with proper datetime serialization
        job_data = sample_extraction_job.model_dump_json()
        mock_redis_client.get.return_value = job_data

        retrieved_job = await job_manager.get_job("test-job-123")

        assert retrieved_job.job_id == sample_extraction_job.job_id
        assert retrieved_job.status == sample_extraction_job.status
        mock_redis_client.get.assert_called_with("job:test-job-123")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_get_job_not_found(self, mock_redis_client):
        """Test retrieving non-existent job."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.get.return_value = None

        with pytest.raises(JobNotFoundError) as exc_info:
            await job_manager.get_job("nonexistent-job")

        assert "nonexistent-job" in str(exc_info.value)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_get_job_invalid_data(self, mock_redis_client):
        """Test retrieving job with corrupted data."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.get.return_value = "invalid json data"

        with pytest.raises(JobNotFoundError):
            await job_manager.get_job("corrupted-job")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_update_job_status_basic(self, mock_redis_client, sample_extraction_job):
        """Test updating job status."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Mock get_job to return sample job
        with patch.object(job_manager, "get_job") as mock_get_job, patch.object(
            job_manager, "_store_job"
        ) as mock_store_job:
            mock_get_job.return_value = sample_extraction_job

            await job_manager.update_job_status(
                "test-job-123", ExtractionStatus.PROCESSING, progress=50.0
            )

            mock_get_job.assert_called_once_with("test-job-123")
            mock_store_job.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_update_job_status_with_result(self, mock_redis_client, sample_extraction_job):
        """Test updating job status with extraction result."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        result = TenderExtractionResult(
            extracted_data={}, confidence_scores={}, extraction_notes={}, processing_metadata={}
        )

        with patch.object(job_manager, "get_job") as mock_get_job, patch.object(
            job_manager, "_store_job"
        ) as mock_store_job:
            mock_get_job.return_value = sample_extraction_job

            await job_manager.update_job_status(
                "test-job-123",
                ExtractionStatus.COMPLETED,
                progress=100.0,
                result=result,
                processing_time=5.2,
                tokens_used=1500,
            )

            mock_store_job.assert_called_once()
            # Verify the job was updated
            updated_job = mock_store_job.call_args[0][0]
            assert updated_job.status == ExtractionStatus.COMPLETED
            assert updated_job.progress == 100.0

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, mock_redis_client):
        """Test listing jobs when none exist."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.zrevrange.return_value = []

        jobs = await job_manager.list_jobs()

        assert jobs == []
        mock_redis_client.zrevrange.assert_called_with("jobs:index", 0, 49)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_list_jobs_with_data(self, mock_redis_client, sample_extraction_job):
        """Test listing jobs with existing data."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.zrevrange.return_value = ["job1", "job2"]

        with patch.object(job_manager, "get_job") as mock_get_job:
            mock_get_job.return_value = sample_extraction_job

            jobs = await job_manager.list_jobs(limit=2)

            assert len(jobs) == 2
            assert mock_get_job.call_count == 2

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, mock_redis_client, sample_extraction_job):
        """Test listing jobs with status filter."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.zrevrange.return_value = ["job1", "job2"]

        # Create jobs with different statuses
        pending_job = sample_extraction_job
        completed_job = ExtractionJob(
            job_id="job2",
            status=ExtractionStatus.COMPLETED,
            created_at=datetime.now(UTC),
            created_at=datetime.now(timezone.utc),
            request=DocumentExtractionRequest(filename="test2.pdf", config_name="default"),
            progress=100.0,
        )

        with patch.object(job_manager, "get_job") as mock_get_job:
            mock_get_job.side_effect = [pending_job, completed_job]

            # Filter for completed jobs only
            jobs = await job_manager.list_jobs(status_filter=ExtractionStatus.COMPLETED)

            assert len(jobs) == 1
            assert jobs[0].status == ExtractionStatus.COMPLETED

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_list_jobs_handles_missing_jobs(self, mock_redis_client):
        """Test listing jobs handles missing job data gracefully."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.zrevrange.return_value = ["missing-job"]

        with patch.object(job_manager, "get_job") as mock_get_job:
            mock_get_job.side_effect = JobNotFoundError("missing-job")

            jobs = await job_manager.list_jobs()

            # Should return empty list, not raise error
            assert jobs == []

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_cancel_job_success(self, mock_redis_client, sample_extraction_job):
        """Test successful job cancellation."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.get.return_value = "rq-job-123"

        with patch.object(job_manager, "get_job") as mock_get_job, patch.object(
            job_manager, "update_job_status"
        ) as mock_update_status, patch.object(
            job_manager, "_cleanup_job_data"
        ) as mock_cleanup, patch.object(
            job_manager, "_get_sync_connection"
        ) as mock_sync_conn, patch(
            "rq.job.Job.fetch"
        ) as mock_job_fetch:
            mock_get_job.return_value = sample_extraction_job

            # Mock RQ job
            mock_rq_job = MagicMock()
            mock_rq_job.get_status.return_value = "queued"
            mock_job_fetch.return_value = mock_rq_job
            mock_sync_conn.return_value.__enter__ = lambda x: None
            mock_sync_conn.return_value.__exit__ = lambda x, y, z, w: None

            result = await job_manager.cancel_job("test-job-123")

            assert result is True
            mock_rq_job.cancel.assert_called_once()
            mock_update_status.assert_called_with("test-job-123", ExtractionStatus.CANCELLED)
            mock_cleanup.assert_called_with("test-job-123")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_cancel_job_already_completed(self, mock_redis_client, sample_extraction_job):
        """Test cancelling already completed job."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Mock completed job
        completed_job = sample_extraction_job
        completed_job.status = ExtractionStatus.COMPLETED

        with patch.object(job_manager, "get_job") as mock_get_job:
            mock_get_job.return_value = completed_job

            result = await job_manager.cancel_job("test-job-123")

            assert result is False

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_cancel_job_rq_failure(self, mock_redis_client, sample_extraction_job):
        """Test job cancellation when RQ operations fail."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        mock_redis_client.get.return_value = "rq-job-123"

        with patch.object(job_manager, "get_job") as mock_get_job, patch.object(
            job_manager, "update_job_status"
        ) as mock_update_status, patch.object(
            job_manager, "_cleanup_job_data"
        ) as mock_cleanup, patch.object(
            job_manager, "_get_sync_connection"
        ) as mock_sync_conn, patch(
            "rq.job.Job.fetch"
        ) as mock_job_fetch:
            mock_get_job.return_value = sample_extraction_job
            mock_job_fetch.side_effect = Exception("RQ error")
            mock_sync_conn.return_value.__enter__ = lambda x: None
            mock_sync_conn.return_value.__exit__ = lambda x, y, z, w: None

            result = await job_manager.cancel_job("test-job-123")

            # Should still succeed overall despite RQ failure
            assert result is True
            mock_update_status.assert_called_with("test-job-123", ExtractionStatus.CANCELLED)
            mock_cleanup.assert_called_with("test-job-123")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_cleanup_job_data(self, mock_redis_client):
        """Test cleaning up job data."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        await job_manager._cleanup_job_data("test-job-123")

        # Verify all associated keys are deleted
        expected_calls = [(("job:test-job-123:files",), {}), (("job:test-job-123:rq_id",), {})]
        mock_redis_client.delete.assert_has_calls(list(expected_calls), any_order=True)

    @pytest.mark.asyncio()
        mock_redis_client.delete.assert_has_calls([call for call in expected_calls], any_order=True)

    @pytest.mark.asyncio
    async def test_delete_job_success(self, mock_redis_client, sample_extraction_job):
        """Test successful job deletion."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        with patch.object(job_manager, "get_job") as mock_get_job, patch.object(
            job_manager, "cancel_job"
        ):
        ) as mock_cancel:
            mock_get_job.return_value = sample_extraction_job

            result = await job_manager.delete_job("test-job-123")

            assert result is True
            # Verify all job data is deleted
            mock_redis_client.delete.assert_called()
            mock_redis_client.zrem.assert_called_with("jobs:index", "test-job-123")

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_delete_job_nonexistent(self, mock_redis_client):
        """Test deleting non-existent job."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        with patch.object(job_manager, "get_job") as mock_get_job:
            mock_get_job.side_effect = JobNotFoundError("test-job-123")

            result = await job_manager.delete_job("test-job-123")

            assert result is False

    @pytest.mark.asyncio()
    async def test_get_job_statistics(self, mock_redis_client, sample_document_request):
    @pytest.mark.asyncio
    async def test_get_job_statistics(self, mock_redis_client):
        """Test getting job statistics."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Mock queue lengths and job counts
        with patch("app.services.job_manager.Queue") as mock_queue_class, patch.object(
            job_manager, "_get_sync_connection"
        ) as mock_sync_conn, patch.object(job_manager, "get_job") as mock_get_job:
        with patch("rq.Queue") as mock_queue_class, patch.object(
            job_manager, "_get_sync_connection"
        ) as mock_sync_conn:
            mock_default_queue = MagicMock()
            mock_high_queue = MagicMock()
            mock_default_queue.__len__ = lambda x: 5
            mock_high_queue.__len__ = lambda x: 2

            mock_queue_class.side_effect = [mock_default_queue, mock_high_queue]

            # Setup context manager for sync connection
            mock_context = MagicMock()
            mock_context.__enter__ = lambda x: None
            mock_context.__exit__ = lambda x, y, z, w: None
            mock_sync_conn.return_value = mock_context

            # Mock Redis operations for job counts
            mock_redis_client.zcard.return_value = 10
            mock_redis_client.zrange.return_value = [f"job-{i}" for i in range(10)]  # 10 job IDs
            mock_redis_client.zcount.side_effect = [
                3,
                2,
                4,
                1,
            ]  # pending, processing, completed, failed

            # Mock get_job to return jobs with different statuses
            from app.models.extraction import ExtractionJob, ExtractionStatus

            # Use the sample request fixture

            mock_jobs = [
                ExtractionJob(
                    job_id="job-0",
                    status=ExtractionStatus.PENDING,
                    created_at=datetime.now(tz=UTC),
                    request=sample_document_request,
                ),
                ExtractionJob(
                    job_id="job-1",
                    status=ExtractionStatus.PROCESSING,
                    created_at=datetime.now(tz=UTC),
                    request=sample_document_request,
                ),
                ExtractionJob(
                    job_id="job-2",
                    status=ExtractionStatus.COMPLETED,
                    created_at=datetime.now(tz=UTC),
                    request=sample_document_request,
                ),
                ExtractionJob(
                    job_id="job-3",
                    status=ExtractionStatus.FAILED,
                    created_at=datetime.now(tz=UTC),
                    request=sample_document_request,
                ),
            ]
            mock_get_job.side_effect = lambda job_id: mock_jobs[
                int(job_id.split("-")[1]) % len(mock_jobs)
            ]

            stats = await job_manager.get_job_statistics()

            assert stats["queue_stats"]["default_queue_length"] == 5
            assert stats["queue_stats"]["high_queue_length"] == 2
            assert stats["queue_stats"]["total_queued"] == 7
            assert stats["total_jobs"] == 10

    @pytest.mark.asyncio()
            stats = await job_manager.get_job_statistics()

            assert stats["default_queue_length"] == 5
            assert stats["high_queue_length"] == 2
            assert stats["total_queued"] == 7
            assert stats["total_jobs"] == 10

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs(self, mock_redis_client):
        """Test cleaning up old jobs."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Mock old job IDs
        old_job_ids = ["old-job-1", "old-job-2", "old-job-3"]
        mock_redis_client.zrangebyscore.return_value = old_job_ids

        with patch.object(job_manager, "get_job", new_callable=AsyncMock) as mock_get_job:
            # Mock get_job to return jobs with completed/failed status (which should be cleaned)
            from app.models.extraction import (
                DocumentExtractionRequest,
                ExtractionJob,
                ExtractionStatus,
            )

            sample_request = DocumentExtractionRequest(filename="test.pdf", prompt="test")

            mock_jobs = [
                ExtractionJob(
                    job_id="old-job-1",
                    status=ExtractionStatus.COMPLETED,
                    created_at=datetime.now(tz=UTC),
                    request=sample_request,
                ),
                ExtractionJob(
                    job_id="old-job-2",
                    status=ExtractionStatus.FAILED,
                    created_at=datetime.now(tz=UTC),
                    request=sample_request,
                ),
                ExtractionJob(
                    job_id="old-job-3",
                    status=ExtractionStatus.CANCELLED,
                    created_at=datetime.now(tz=UTC),
                    request=sample_request,
                ),
            ]
            mock_get_job.side_effect = lambda job_id: mock_jobs[int(job_id.split("-")[2]) - 1]

            # Mock Redis delete operations to return success
            mock_redis_client.delete.return_value = 1
            mock_redis_client.zrem.return_value = 1
        with patch.object(job_manager, "delete_job", new_callable=AsyncMock) as mock_delete_job:
            mock_delete_job.return_value = True

            cleaned_count = await job_manager.cleanup_old_jobs(older_than_days=7)

            assert cleaned_count == 3
            assert mock_get_job.call_count == 3
            # Verify Redis cleanup calls were made
            assert (
                mock_redis_client.delete.call_count == 6
            )  # 2 delete calls per job (job data + rq_id)
            assert mock_redis_client.zrem.call_count == 3  # 1 zrem call per job
            assert mock_delete_job.call_count == 3


class TestJobWorkerManager:
    """Test JobWorkerManager class functionality."""

    def test_worker_manager_initialization(self):
        """Test JobWorkerManager initialization."""
        worker_manager = JobWorkerManager()

        assert worker_manager.redis_url is not None
        assert worker_manager.workers == []

    def test_start_workers(self):
        """Test starting RQ workers."""
        worker_manager = JobWorkerManager()

        with patch("app.services.job_manager.Connection") as mock_connection, patch(
            "app.services.job_manager.Queue"
        ) as mock_queue_class, patch("app.services.job_manager.Worker") as mock_worker_class, patch(
            "app.services.job_manager.redis.from_url"
        with patch("rq.Connection") as mock_connection, patch(
            "rq.Queue"
        ) as mock_queue_class, patch("rq.Worker") as mock_worker_class, patch(
            "redis.from_url"
        ) as mock_redis_from_url:
            # Setup connection context manager
            mock_connection.return_value.__enter__ = lambda x: None
            mock_connection.return_value.__exit__ = lambda x, y, z, w: None

            # Setup Redis connection mock
            mock_redis_from_url.return_value = MagicMock()

            # Setup queue mocks
            mock_high_queue = MagicMock()
            mock_default_queue = MagicMock()
            mock_queue_class.side_effect = [mock_high_queue, mock_default_queue]

            # Setup worker mocks
            mock_worker1 = MagicMock()
            mock_worker2 = MagicMock()
            mock_worker_class.side_effect = [mock_worker1, mock_worker2]

            worker_manager.start_workers(num_workers=2)

            assert len(worker_manager.workers) == 2
            assert mock_worker_class.call_count == 2

    def test_stop_workers(self):
        """Test stopping RQ workers."""
        worker_manager = JobWorkerManager()

        # Add mock workers
        mock_worker1 = MagicMock()
        mock_worker2 = MagicMock()
        worker_manager.workers = [mock_worker1, mock_worker2]

        worker_manager.stop_workers()

        mock_worker1.stop.assert_called_once()
        mock_worker2.stop.assert_called_once()
        assert worker_manager.workers == []

    def test_stop_workers_with_errors(self):
        """Test stopping workers handles errors gracefully."""
        worker_manager = JobWorkerManager()

        # Add mock worker that fails to stop
        mock_worker = MagicMock()
        mock_worker.stop.side_effect = Exception("Stop failed")
        worker_manager.workers = [mock_worker]

        # Should not raise exception
        worker_manager.stop_workers()

        assert worker_manager.workers == []


class TestJobManagerGlobalFunctions:
    """Test global job manager functions."""

    def test_get_job_manager_singleton(self):
        """Test get_job_manager returns same instance."""
        # Reset global instance
        import app.services.job_manager

        app.services.job_manager._job_manager = None

        manager1 = get_job_manager()
        manager2 = get_job_manager()

        assert manager1 is manager2
        assert isinstance(manager1, JobManager)

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_initialize_job_manager(self):
        """Test initialize_job_manager function."""
        with patch("app.services.job_manager.get_job_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_get_manager.return_value = mock_manager

            await initialize_job_manager()

            mock_manager.initialize.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_cleanup_job_manager(self):
        """Test cleanup_job_manager function."""
        # Set up global instance
        import app.services.job_manager

        mock_manager = AsyncMock()
        app.services.job_manager._job_manager = mock_manager

        await cleanup_job_manager()

        mock_manager.cleanup.assert_called_once()
        assert app.services.job_manager._job_manager is None

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_cleanup_job_manager_no_instance(self):
        """Test cleanup_job_manager with no existing instance."""
        # Reset global instance
        import app.services.job_manager

        app.services.job_manager._job_manager = None

        # Should not raise error
        await cleanup_job_manager()

        assert app.services.job_manager._job_manager is None


class TestJobManagerIntegrationScenarios:
    """Integration-style tests for complete job workflows."""

    @pytest.mark.asyncio()
    async def test_complete_job_lifecycle(self, mock_redis_client):
        """Test complete job lifecycle from creation to completion."""
        job_manager = JobManager()

        # Mock the Redis client methods with actual Mock objects
        with patch.object(
            mock_redis_client, "set", wraps=mock_redis_client.set
        ) as mock_set, patch.object(
            mock_redis_client, "zadd", wraps=mock_redis_client.zadd
        ) as mock_zadd:
            job_manager._redis_client = mock_redis_client

            # Create request
            request = DocumentExtractionRequest(
                filename="lifecycle_test.pdf", config_name="default"
            )

            file_contents = {"lifecycle_test.pdf": b"test content"}

            with patch.object(job_manager, "_enqueue_job") as mock_enqueue:
                # 1. Create job
                job_id = await job_manager.create_extraction_job(
                    request, file_contents=file_contents
                )

                # 2. Verify job was created and stored
                mock_set.assert_called()
                mock_zadd.assert_called()
                mock_enqueue.assert_called_once()
    @pytest.mark.asyncio
    async def test_complete_job_lifecycle(self, mock_redis_client):
        """Test complete job lifecycle from creation to completion."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Create request
        request = DocumentExtractionRequest(filename="lifecycle_test.pdf", config_name="default")

        file_contents = {"lifecycle_test.pdf": b"test content"}

        with patch.object(job_manager, "_enqueue_job") as mock_enqueue:
            # 1. Create job
            job_id = await job_manager.create_extraction_job(request, file_contents=file_contents)

            # 2. Verify job was created and stored
            mock_redis_client.set.assert_called()
            mock_redis_client.zadd.assert_called()
            mock_enqueue.assert_called_once()

            # 3. Simulate job processing updates
            with patch.object(job_manager, "get_job") as mock_get_job, patch.object(
                job_manager, "_store_job"
            ) as mock_store_job:
                # Create mock job for updates
                job = ExtractionJob(
                    job_id=job_id,
                    status=ExtractionStatus.PENDING,
                    created_at=datetime.now(UTC),
                    created_at=datetime.now(timezone.utc),
                    request=request,
                    progress=0.0,
                )
                mock_get_job.return_value = job

                # Update to processing
                await job_manager.update_job_status(job_id, ExtractionStatus.PROCESSING, 25.0)

                # Update to completed with result
                result = TenderExtractionResult(
                    extracted_data={},
                    confidence_scores={},
                    extraction_notes={},
                    processing_metadata={},
                )
                await job_manager.update_job_status(
                    job_id, ExtractionStatus.COMPLETED, 100.0, result=result
                )

                # Verify updates were stored
                assert mock_store_job.call_count == 2

    @pytest.mark.asyncio()
    async def test_batch_job_management(self, mock_redis_client):
        """Test managing multiple jobs in batch."""
        job_manager = JobManager()

        # Mock the Redis client methods with actual Mock objects
        with patch.object(
            mock_redis_client, "set", wraps=mock_redis_client.set
        ) as mock_set, patch.object(
            mock_redis_client, "zadd", wraps=mock_redis_client.zadd
        ) as mock_zadd, patch.object(
            mock_redis_client, "zrevrange", wraps=mock_redis_client.zrevrange
        ) as mock_zrevrange:
            job_manager._redis_client = mock_redis_client

            # Create multiple jobs
            job_ids = []
            requests = []

            with patch.object(job_manager, "_enqueue_job"):
                for i in range(3):
                    request = DocumentExtractionRequest(
                        filename=f"batch_doc_{i}.pdf", config_name="default"
                    )
                    requests.append(request)

                    job_id = await job_manager.create_extraction_job(request, priority=i)
                    job_ids.append(job_id)

            # Verify all jobs were created
            assert len(job_ids) == 3
            assert mock_set.call_count >= 3  # Job storage calls
            assert mock_zadd.call_count >= 3  # Index update calls

            # Test listing jobs
            mock_zrevrange.return_value = job_ids
    @pytest.mark.asyncio
    async def test_batch_job_management(self, mock_redis_client):
        """Test managing multiple jobs in batch."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Create multiple jobs
        job_ids = []
        requests = []

        with patch.object(job_manager, "_enqueue_job"):
            for i in range(3):
                request = DocumentExtractionRequest(
                    filename=f"batch_doc_{i}.pdf", config_name="default"
                )
                requests.append(request)

                job_id = await job_manager.create_extraction_job(request, priority=i)
                job_ids.append(job_id)

        # Verify all jobs were created
        assert len(job_ids) == 3
        assert mock_redis_client.set.call_count >= 3  # Job storage calls
        assert mock_redis_client.zadd.call_count >= 3  # Index update calls

        # Test listing jobs
        mock_redis_client.zrevrange.return_value = job_ids

        with patch.object(job_manager, "get_job") as mock_get_job:
            # Create mock jobs for listing
            mock_jobs = [
                ExtractionJob(
                    job_id=job_id,
                    status=ExtractionStatus.PENDING,
                    created_at=datetime.now(UTC),
                    created_at=datetime.now(timezone.utc),
                    request=req,
                    progress=0.0,
                )
                for job_id, req in zip(job_ids, requests)
            ]
            mock_get_job.side_effect = mock_jobs

            jobs = await job_manager.list_jobs(limit=10)

            assert len(jobs) == 3
            assert mock_get_job.call_count == 3

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, mock_redis_client):
        """Test error recovery in various scenarios."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Scenario 1: Redis connection failure during operation
        with patch.object(mock_redis_client, "get", side_effect=Exception("Redis connection lost")):
            with pytest.raises(Exception, match="Redis connection lost"):
                await job_manager.get_job("test-job")

        # Scenario 2: Corrupted job data recovery
        with patch.object(mock_redis_client, "get", return_value="corrupted json data {["):
            with pytest.raises(JobNotFoundError):
                await job_manager.get_job("corrupted-job")

        # Scenario 3: Missing file contents handling
        with patch.object(mock_redis_client, "get", return_value=None):
            file_contents = await job_manager.get_file_contents("missing-files-job")
            assert file_contents == {}

    @pytest.mark.asyncio()
    async def test_concurrent_job_operations(self, mock_redis_client):
        """Test concurrent job operations."""
        job_manager = JobManager()

        # Mock the Redis client methods with actual Mock objects
        with patch.object(
            mock_redis_client, "set", wraps=mock_redis_client.set
        ) as mock_set, patch.object(
            mock_redis_client, "zadd", wraps=mock_redis_client.zadd
        ) as mock_zadd:
            job_manager._redis_client = mock_redis_client

            # Simulate concurrent job creation
            requests = [
                DocumentExtractionRequest(filename=f"concurrent_{i}.pdf", config_name="default")
                for i in range(5)
            ]

            with patch.object(job_manager, "_enqueue_job"):
                # Create jobs concurrently
                tasks = [
                    job_manager.create_extraction_job(req, priority=i)
                    for i, req in enumerate(requests)
                ]

                job_ids = await asyncio.gather(*tasks)

                assert len(job_ids) == 5
                assert len(set(job_ids)) == 5  # All unique UUIDs

                # Verify all jobs were stored (multiple Redis calls expected)
                assert mock_set.call_count >= 5
                assert mock_zadd.call_count >= 5
        mock_redis_client.get.side_effect = Exception("Redis connection lost")

        with pytest.raises(Exception):
            await job_manager.get_job("test-job")

        # Reset side_effect for next scenario
        mock_redis_client.get.side_effect = None

        # Scenario 2: Corrupted job data recovery
        mock_redis_client.get.return_value = "corrupted json data {["

        with pytest.raises(JobNotFoundError):
            await job_manager.get_job("corrupted-job")

        # Scenario 3: Missing file contents handling
        mock_redis_client.get.return_value = None

        file_contents = await job_manager.get_file_contents("missing-files-job")
        assert file_contents == {}

    @pytest.mark.asyncio
    async def test_concurrent_job_operations(self, mock_redis_client):
        """Test concurrent job operations."""
        job_manager = JobManager()
        job_manager._redis_client = mock_redis_client

        # Simulate concurrent job creation
        requests = [
            DocumentExtractionRequest(filename=f"concurrent_{i}.pdf", config_name="default")
            for i in range(5)
        ]

        with patch.object(job_manager, "_enqueue_job"):
            # Create jobs concurrently
            tasks = [
                job_manager.create_extraction_job(req, priority=i) for i, req in enumerate(requests)
            ]

            job_ids = await asyncio.gather(*tasks)

            assert len(job_ids) == 5
            assert len(set(job_ids)) == 5  # All unique UUIDs

            # Verify all jobs were stored (multiple Redis calls expected)
            assert mock_redis_client.set.call_count >= 5
            assert mock_redis_client.zadd.call_count >= 5
