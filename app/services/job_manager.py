import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import redis as redis_sync
import redis.asyncio as redis
import rq
from rq import Connection, Queue, Worker
from rq.job import Job

from app.config import settings
from app.core.exceptions import JobNotFoundError, ServiceUnavailableError
from app.models.extraction import (
    BatchExtractionRequest,
    DocumentExtractionRequest,
    ExtractionJob,
    ExtractionStatus,
    TenderExtractionResult,
)

logger = logging.getLogger(__name__)


class JobManager:
    """Manages document extraction jobs using Redis and RQ."""

    def __init__(self):
        self.redis_url = settings.redis_url
        self.max_concurrent_jobs = settings.max_concurrent_jobs
        self._redis_client: Optional[redis.Redis] = None
        self._connection: Optional[redis.ConnectionPool] = None

    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self._connection = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True,
            )
            self._redis_client = redis.Redis(connection_pool=self._connection)

            # Test connection
            await self._redis_client.ping()
            logger.info("Redis connection established successfully")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ServiceUnavailableError(f"Job queue unavailable: {str(e)}")

    async def cleanup(self):
        """Clean up Redis connections."""
        if self._redis_client:
            await self._redis_client.close()
        if self._connection:
            await self._connection.disconnect()

    def _get_sync_connection(self):
        """Get synchronous Redis connection for RQ."""
        return rq.Connection(redis_sync.from_url(self.redis_url))

    async def create_extraction_job(
        self,
        request: Union[DocumentExtractionRequest, BatchExtractionRequest],
        priority: int = 0,
        file_contents: Optional[Dict[str, bytes]] = None,
    ) -> str:
        """Create a new document extraction job."""

        job_id = str(uuid.uuid4())

        # Create job record
        job = ExtractionJob(
            job_id=job_id,
            status=ExtractionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            request=request,
            progress=0.0,
        )

        # Store job in Redis
        await self._store_job(job)

        # Store file contents if provided
        if file_contents:
            await self._store_file_contents(job_id, file_contents)

        # Queue the job for processing
        await self._enqueue_job(job_id, request, priority)

        logger.info(f"Created extraction job: {job_id}")
        return job_id

    async def _store_job(self, job: ExtractionJob) -> None:
        """Store job in Redis."""
        job_key = f"job:{job.job_id}"
        job_data = job.model_dump_json()

        await self._redis_client.set(job_key, job_data)
        await self._redis_client.expire(job_key, 86400 * 7)  # 7 days TTL

        # Add to job index
        await self._redis_client.zadd("jobs:index", {job.job_id: job.created_at.timestamp()})

    async def _store_file_contents(self, job_id: str, file_contents: Dict[str, bytes]) -> None:
        """Store file contents in Redis for worker access."""
        import base64

        # Convert bytes to base64 for JSON serialization
        encoded_contents = {}
        for filename, content in file_contents.items():
            encoded_contents[filename] = base64.b64encode(content).decode("utf-8")

        content_key = f"job:{job_id}:files"
        await self._redis_client.set(content_key, json.dumps(encoded_contents))
        await self._redis_client.expire(content_key, 86400 * 7)  # 7 days TTL

    async def get_file_contents(self, job_id: str) -> Dict[str, bytes]:
        """Retrieve file contents for a job."""
        import base64

        content_key = f"job:{job_id}:files"
        encoded_data = await self._redis_client.get(content_key)

        if not encoded_data:
            return {}

        # Decode base64 back to bytes
        encoded_contents = json.loads(encoded_data)
        file_contents = {}
        for filename, encoded_content in encoded_contents.items():
            file_contents[filename] = base64.b64decode(encoded_content.encode("utf-8"))

        return file_contents

    async def _enqueue_job(
        self,
        job_id: str,
        request: Union[DocumentExtractionRequest, BatchExtractionRequest],
        priority: int,
    ) -> None:
        """Enqueue job for background processing."""

        # Use RQ for job queuing
        with self._get_sync_connection():
            # Choose queue based on job type and priority
            queue_name = "high" if priority > 5 else "default"
            queue = Queue(queue_name)

            # Enqueue the job
            rq_job = queue.enqueue(
                "app.services.extraction_worker.process_extraction_job",
                job_id,
                request.model_dump(),
                job_timeout="10m",
                result_ttl=86400 * 7,  # 7 days
            )

        # Store RQ job ID for reference (outside the sync context)
        await self._redis_client.set(f"job:{job_id}:rq_id", rq_job.id)
        
        # Set up fallback processing in case RQ workers fail (e.g., on macOS)
        asyncio.create_task(self._monitor_and_fallback_job(job_id, request, rq_job.id))

    async def get_job(self, job_id: str) -> ExtractionJob:
        """Retrieve job by ID."""
        job_key = f"job:{job_id}"
        job_data = await self._redis_client.get(job_key)

        if not job_data:
            raise JobNotFoundError(job_id)

        try:
            job_dict = json.loads(job_data)
            return ExtractionJob(**job_dict)
        except Exception as e:
            logger.error(f"Failed to parse job data for {job_id}: {e}")
            raise JobNotFoundError(job_id)

    async def update_job_status(
        self,
        job_id: str,
        status: ExtractionStatus,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
        result: Optional[Union[TenderExtractionResult, List[TenderExtractionResult]]] = None,
        processing_time: Optional[float] = None,
        tokens_used: Optional[int] = None,
    ) -> None:
        """Update job status and progress."""

        job = await self.get_job(job_id)

        # Update fields
        job.status = status
        if progress is not None:
            job.progress = progress
        if error_message:
            job.error_message = error_message
        if result:
            job.result = result
        if processing_time:
            job.processing_time = processing_time
        if tokens_used:
            job.tokens_used = tokens_used

        # Update timestamps
        now = datetime.now(timezone.utc)
        if status == ExtractionStatus.PROCESSING and not job.started_at:
            job.started_at = now
        elif status in [ExtractionStatus.COMPLETED, ExtractionStatus.FAILED]:
            job.completed_at = now
            if status == ExtractionStatus.COMPLETED:
                job.progress = 100.0

        # Store updated job
        await self._store_job(job)

        logger.info(f"Updated job {job_id}: status={status.value}, progress={job.progress}%")

    async def list_jobs(
        self, limit: int = 50, offset: int = 0, status_filter: Optional[ExtractionStatus] = None
    ) -> List[ExtractionJob]:
        """List jobs with optional filtering."""

        # Get job IDs from index (sorted by creation time, newest first)
        job_ids = await self._redis_client.zrevrange("jobs:index", offset, offset + limit - 1)

        if not job_ids:
            return []

        # Retrieve job data
        jobs = []
        for job_id in job_ids:
            try:
                job = await self.get_job(job_id)
                if status_filter is None or job.status == status_filter:
                    jobs.append(job)
            except JobNotFoundError:
                # Job might have been cleaned up
                continue

        return jobs

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or processing job."""

        job = await self.get_job(job_id)

        if job.status in [ExtractionStatus.COMPLETED, ExtractionStatus.FAILED]:
            return False  # Cannot cancel completed jobs

        # Cancel RQ job if it exists
        rq_job_id = await self._redis_client.get(f"job:{job_id}:rq_id")
        if rq_job_id:
            try:
                with self._get_sync_connection():
                    rq_job = Job.fetch(rq_job_id)
                    if rq_job.get_status() in ["queued", "started"]:
                        rq_job.cancel()
                        logger.info(f"Cancelled RQ job: {rq_job_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel RQ job {rq_job_id}: {e}")

        # Update job status
        await self.update_job_status(job_id, ExtractionStatus.CANCELLED)

        # Clean up associated data
        await self._cleanup_job_data(job_id)

        logger.info(f"Cancelled job: {job_id}")
        return True

    async def _cleanup_job_data(self, job_id: str) -> None:
        """Clean up all data associated with a job."""
        try:
            # Remove file contents
            await self._redis_client.delete(f"job:{job_id}:files")
            # Remove RQ job ID reference
            await self._redis_client.delete(f"job:{job_id}:rq_id")
            logger.debug(f"Cleaned up data for job: {job_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup data for job {job_id}: {e}")

    async def delete_job(self, job_id: str) -> bool:
        """Completely delete a job and all its data."""
        try:
            # First try to cancel if it's still running
            job = await self.get_job(job_id)
            if job.status in [ExtractionStatus.PENDING, ExtractionStatus.PROCESSING]:
                await self.cancel_job(job_id)

            # Remove all job data
            await self._redis_client.delete(f"job:{job_id}")
            await self._redis_client.delete(f"job:{job_id}:files")
            await self._redis_client.delete(f"job:{job_id}:rq_id")

            # Remove from job index
            await self._redis_client.zrem("jobs:index", job_id)

            logger.info(f"Deleted job: {job_id}")
            return True

        except JobNotFoundError:
            # Job already doesn't exist
            return False
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False

    async def get_job_statistics(self) -> Dict[str, Any]:
        """Get job queue statistics."""

        # Get queue lengths
        with self._get_sync_connection():
            default_queue = Queue("default")
            high_queue = Queue("high")

            queue_stats = {
                "default_queue_length": len(default_queue),
                "high_queue_length": len(high_queue),
                "total_queued": len(default_queue) + len(high_queue),
            }

        # Get job status counts
        status_counts = {status.value: 0 for status in ExtractionStatus}

        # This is a simplified implementation
        # In production, you might want to maintain separate counters
        job_ids = await self._redis_client.zrange("jobs:index", 0, -1)

        for job_id in job_ids[-100:]:  # Check last 100 jobs for efficiency
            try:
                job = await self.get_job(job_id)
                status_counts[job.status.value] += 1
            except JobNotFoundError:
                continue

        return {
            "queue_stats": queue_stats,
            "status_counts": status_counts,
            "total_jobs": len(job_ids),
        }

    async def cleanup_old_jobs(self, older_than_days: int = 7) -> int:
        """Clean up old completed jobs."""

        cutoff_timestamp = time.time() - (older_than_days * 24 * 60 * 60)

        # Get old job IDs
        old_job_ids = await self._redis_client.zrangebyscore("jobs:index", 0, cutoff_timestamp)

        cleaned_count = 0
        for job_id in old_job_ids:
            try:
                job = await self.get_job(job_id)
                if job.status in [
                    ExtractionStatus.COMPLETED,
                    ExtractionStatus.FAILED,
                    ExtractionStatus.CANCELLED,
                ]:
                    # Delete job data
                    await self._redis_client.delete(f"job:{job_id}")
                    await self._redis_client.delete(f"job:{job_id}:rq_id")
                    await self._redis_client.zrem("jobs:index", job_id)
                    cleaned_count += 1
            except JobNotFoundError:
                # Already cleaned up
                await self._redis_client.zrem("jobs:index", job_id)
                cleaned_count += 1

        logger.info(f"Cleaned up {cleaned_count} old jobs")
        return cleaned_count

    async def _monitor_and_fallback_job(
        self, 
        job_id: str, 
        request: Union[DocumentExtractionRequest, BatchExtractionRequest],
        rq_job_id: str
    ) -> None:
        """Monitor RQ job and fall back to direct processing if it fails."""
        
        try:
            # Wait a bit to see if RQ processes the job
            await asyncio.sleep(5)
            
            # Check if job is still pending
            job = await self.get_job(job_id)
            if job.status != ExtractionStatus.PENDING:
                # Job was processed by RQ worker
                return
                
            # Check RQ job status
            with self._get_sync_connection():
                from rq.job import Job
                try:
                    rq_job = Job.fetch(rq_job_id)
                    rq_status = rq_job.get_status()
                    
                    if rq_status == "failed":
                        logger.warning(f"RQ job {rq_job_id} failed, falling back to direct processing")
                        await self._process_job_directly(job_id, request)
                    elif rq_status in ["queued", "started"]:
                        # Job is being processed, wait longer
                        await asyncio.sleep(30)
                        # Check again
                        job = await self.get_job(job_id)
                        if job.status == ExtractionStatus.PENDING:
                            logger.warning(f"RQ job {rq_job_id} stuck, falling back to direct processing")
                            await self._process_job_directly(job_id, request)
                        
                except Exception as e:
                    logger.warning(f"Could not check RQ job status: {e}, falling back to direct processing")
                    await self._process_job_directly(job_id, request)
                    
        except Exception as e:
            logger.error(f"Error in job monitoring for {job_id}: {e}")

    async def _process_job_directly(
        self, 
        job_id: str, 
        request: Union[DocumentExtractionRequest, BatchExtractionRequest]
    ) -> None:
        """Process job directly without RQ worker."""
        
        try:
            logger.info(f"Starting direct processing for job: {job_id}")
            
            # Import here to avoid circular imports
            from app.services.extraction_worker import ExtractionService
            
            # Create service and process
            service = ExtractionService()
            
            # Get file contents
            file_contents = await self.get_file_contents(job_id)
            
            if isinstance(request, BatchExtractionRequest):
                # Update status to processing
                await self.update_job_status(job_id, ExtractionStatus.PROCESSING, 10.0)
                
                # Process batch
                available_documents = {
                    filename: content
                    for filename, content in file_contents.items()
                    if content is not None
                }
                
                if available_documents:
                    result = await service._process_multiple_documents(available_documents, request)
                    await self.update_job_status(
                        job_id, ExtractionStatus.COMPLETED, progress=100.0, result=[result]
                    )
                    logger.info(f"Successfully completed direct processing for job: {job_id}")
                else:
                    raise ValueError("No document content available")
            else:
                # Handle single document processing
                await self.update_job_status(job_id, ExtractionStatus.PROCESSING, 50.0)
                # TODO: Implement single document processing
                raise NotImplementedError("Single document processing not implemented yet")
                
        except Exception as e:
            logger.error(f"Direct processing failed for job {job_id}: {e}")
            await self.update_job_status(
                job_id, 
                ExtractionStatus.FAILED, 
                error_message=f"Processing failed: {str(e)}"
            )


class JobWorkerManager:
    """Manages RQ workers for job processing."""

    def __init__(self):
        self.redis_url = settings.redis_url
        self.workers: List[Worker] = []

    def start_workers(self, num_workers: int = 2):
        """Start RQ workers."""

        with Connection(redis.from_url(self.redis_url)):
            # Create queues
            high_queue = Queue("high")
            default_queue = Queue("default")

            # Start workers
            for i in range(num_workers):
                worker = Worker([high_queue, default_queue], name=f"worker-{i+1}")
                self.workers.append(worker)

                # In a real application, you'd run this in a separate process
                # worker.work(burst=False)

        logger.info(f"Started {num_workers} job workers")

    def stop_workers(self):
        """Stop all workers."""
        for worker in self.workers:
            try:
                worker.stop()
            except Exception as e:
                logger.warning(f"Error stopping worker: {e}")

        self.workers.clear()
        logger.info("Stopped all job workers")


# Global job manager instance
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get the global job manager instance."""
    global _job_manager

    if _job_manager is None:
        _job_manager = JobManager()

    return _job_manager


async def initialize_job_manager():
    """Initialize the job manager."""
    manager = get_job_manager()
    await manager.initialize()


async def cleanup_job_manager():
    """Cleanup the job manager."""
    global _job_manager
    if _job_manager:
        await _job_manager.cleanup()
        _job_manager = None
