import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from dataclasses import asdict
import redis.asyncio as redis
import rq
from rq import Worker, Queue, Connection
from rq.job import Job

from app.config import settings
from app.models.extraction import (
    ExtractionJob,
    ExtractionStatus,
    DocumentExtractionRequest,
    BatchExtractionRequest,
    TenderExtractionResult
)
from app.core.exceptions import JobNotFoundError, ServiceUnavailableError

logger = logging.getLogger(__name__)


class JobManager:
    """Manages document extraction jobs using Redis and RQ."""
    
    def __init__(self):
        self.redis_url = settings.redis.url
        self.max_concurrent_jobs = settings.processing.max_concurrent_jobs
        self._redis_client: Optional[redis.Redis] = None
        self._connection: Optional[redis.ConnectionPool] = None
        
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self._connection = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=settings.redis.max_connections,
                decode_responses=True
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
        return rq.Connection(redis.from_url(self.redis_url))
    
    async def create_extraction_job(
        self,
        request: Union[DocumentExtractionRequest, BatchExtractionRequest],
        priority: int = 0
    ) -> str:
        """Create a new document extraction job."""
        
        job_id = str(uuid.uuid4())
        
        # Create job record
        job = ExtractionJob(
            job_id=job_id,
            status=ExtractionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            request=request,
            progress=0.0
        )
        
        # Store job in Redis
        await self._store_job(job)
        
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
        await self._redis_client.zadd(
            "jobs:index",
            {job.job_id: job.created_at.timestamp()}
        )
    
    async def _enqueue_job(
        self,
        job_id: str,
        request: Union[DocumentExtractionRequest, BatchExtractionRequest],
        priority: int
    ) -> None:
        """Enqueue job for background processing."""
        
        # Use RQ for job queuing
        with self._get_sync_connection():
            # Choose queue based on job type and priority
            queue_name = "high" if priority > 5 else "default"
            queue = Queue(queue_name)
            
            # Enqueue the job
            rq_job = queue.enqueue(
                'app.services.extraction_worker.process_extraction_job',
                job_id,
                request.model_dump(),
                job_timeout='10m',
                result_ttl=86400 * 7  # 7 days
            )
            
            # Store RQ job ID for reference
            await self._redis_client.set(f"job:{job_id}:rq_id", rq_job.id)
    
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
        tokens_used: Optional[int] = None
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
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[ExtractionStatus] = None
    ) -> List[ExtractionJob]:
        """List jobs with optional filtering."""
        
        # Get job IDs from index (sorted by creation time, newest first)
        job_ids = await self._redis_client.zrevrange(
            "jobs:index",
            offset,
            offset + limit - 1
        )
        
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
                    rq_job.cancel()
            except Exception as e:
                logger.warning(f"Failed to cancel RQ job {rq_job_id}: {e}")
        
        # Update job status
        await self.update_job_status(job_id, ExtractionStatus.CANCELLED)
        
        logger.info(f"Cancelled job: {job_id}")
        return True
    
    async def get_job_statistics(self) -> Dict[str, Any]:
        """Get job queue statistics."""
        
        # Get queue lengths
        with self._get_sync_connection():
            default_queue = Queue('default')
            high_queue = Queue('high')
            
            queue_stats = {
                "default_queue_length": len(default_queue),
                "high_queue_length": len(high_queue),
                "total_queued": len(default_queue) + len(high_queue)
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
            "total_jobs": len(job_ids)
        }
    
    async def cleanup_old_jobs(self, older_than_days: int = 7) -> int:
        """Clean up old completed jobs."""
        
        cutoff_timestamp = time.time() - (older_than_days * 24 * 60 * 60)
        
        # Get old job IDs
        old_job_ids = await self._redis_client.zrangebyscore(
            "jobs:index",
            0,
            cutoff_timestamp
        )
        
        cleaned_count = 0
        for job_id in old_job_ids:
            try:
                job = await self.get_job(job_id)
                if job.status in [ExtractionStatus.COMPLETED, ExtractionStatus.FAILED, ExtractionStatus.CANCELLED]:
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


class JobWorkerManager:
    """Manages RQ workers for job processing."""
    
    def __init__(self):
        self.redis_url = settings.redis.url
        self.workers: List[Worker] = []
    
    def start_workers(self, num_workers: int = 2):
        """Start RQ workers."""
        
        with Connection(redis.from_url(self.redis_url)):
            # Create queues
            high_queue = Queue('high')
            default_queue = Queue('default')
            
            # Start workers
            for i in range(num_workers):
                worker = Worker(
                    [high_queue, default_queue],
                    name=f"worker-{i+1}"
                )
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