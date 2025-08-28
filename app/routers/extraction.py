import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import settings
from app.core.exceptions import (
    DocumentTooLargeError,
    TenderExtractionException,
    UnsupportedDocumentFormatError,
    map_to_http_exception,
)
from app.models.extraction import (
    BatchExtractionRequest,
    DocumentExtractionRequest,
    ExtractionJob,
    ExtractionStatus,
)
from app.services.job_manager import JobManager, get_job_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["extraction"])


@router.post("/extract/batch", response_model=dict)
async def extract_batch(
    files: List[UploadFile] = File(...),
    config_name: str = Form(default="default"),
    template_override: Optional[str] = Form(None),
    enable_multimodal: bool = Form(default=True),
    priority: int = Form(default=0, ge=0, le=10),
    job_manager: JobManager = Depends(get_job_manager),
):
    """
    Extract structured data from multiple documents as a batch job.

    Returns a job ID that can be used to track progress and retrieve results.
    """
    try:
        # Validate batch size
        if len(files) > settings.batch_size_limit:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size exceeds limit of {settings.batch_size_limit} documents",
            )

        # Validate each file and store content
        total_size = 0
        document_requests = []
        file_contents = {}  # Store file contents by filename

        for file in files:
            if file.size and file.size > settings.max_file_size:
                raise DocumentTooLargeError(file.size, settings.max_file_size)

            # Read and store file content (in production, you'd store in object storage)
            content = await file.read()
            total_size += len(content)

            if len(content) > settings.max_file_size:
                raise DocumentTooLargeError(len(content), settings.max_file_size)

            filename = file.filename or f"document_{len(document_requests) + 1}"

            # Store file content for worker access
            file_contents[filename] = content

            document_requests.append(
                DocumentExtractionRequest(
                    filename=filename,
                    content_type=file.content_type,
                    config_name=config_name,
                    template_override=template_override,
                    enable_multimodal=enable_multimodal,
                )
            )

        # Create batch request
        batch_request = BatchExtractionRequest(documents=document_requests, priority=priority)

        # Create and queue job with file contents
        job_id = await job_manager.create_extraction_job(batch_request, priority, file_contents)

        return {
            "job_id": job_id,
            "status": "queued",
            "message": f"Batch job created with {len(files)} documents",
            "estimated_completion": "5-10 minutes",  # This would be calculated based on queue
        }

    except TenderExtractionException as e:
        logger.error(f"Batch extraction failed: {e}")
        raise map_to_http_exception(e)

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error in batch extraction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs/{job_id}", response_model=ExtractionJob)
async def get_job_status(job_id: str, job_manager: JobManager = Depends(get_job_manager)):
    """
    Get the status and results of an extraction job.
    """
    try:
        job = await job_manager.get_job(job_id)
        return job

    except TenderExtractionException as e:
        raise map_to_http_exception(e)

    except Exception as e:
        logger.error(f"Error retrieving job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str, force: bool = False, job_manager: JobManager = Depends(get_job_manager)
):
    """
    Delete an extraction job completely.

    - If force=false (default): Only cancels pending/processing jobs
    - If force=true: Completely removes job and all its data
    """
    try:
        if force:
            # Completely delete the job
            deleted = await job_manager.delete_job(job_id)
            if deleted:
                return {"message": f"Job {job_id} has been deleted permanently"}
            else:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        else:
            # Just cancel the job
            cancelled = await job_manager.cancel_job(job_id)
            if cancelled:
                return {"message": f"Job {job_id} has been cancelled"}
            else:
                return {"message": f"Job {job_id} cannot be cancelled (already completed)"}

    except TenderExtractionException as e:
        raise map_to_http_exception(e)

    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs", response_model=List[ExtractionJob])
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[ExtractionStatus] = None,
    job_manager: JobManager = Depends(get_job_manager),
):
    """
    List extraction jobs with optional filtering.
    """
    try:
        if limit > 100:
            limit = 100  # Cap the limit

        jobs = await job_manager.list_jobs(limit=limit, offset=offset, status_filter=status)

        return jobs

    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs/{job_id}/export")
async def export_job_results(
    job_id: str, format: str = "json", job_manager: JobManager = Depends(get_job_manager)
):
    """
    Export job results in different formats (JSON, CSV, Excel).
    """
    try:
        job = await job_manager.get_job(job_id)

        if job.status != ExtractionStatus.COMPLETED:
            raise HTTPException(
                status_code=400, detail=f"Job is not completed. Current status: {job.status.value}"
            )

        if not job.result:
            raise HTTPException(status_code=404, detail="No results found for this job")

        # For now, we'll just return JSON
        # In production, you'd implement CSV/Excel export
        if format.lower() == "json":
            return JSONResponse(
                content=job.result.dict() if hasattr(job.result, "dict") else job.result,
                headers={"Content-Disposition": f"attachment; filename={job_id}_results.json"},
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Format '{format}' not supported. Supported formats: json"
            )

    except TenderExtractionException as e:
        raise map_to_http_exception(e)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error exporting job results {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/statistics")
async def get_extraction_statistics(job_manager: JobManager = Depends(get_job_manager)):
    """
    Get extraction service statistics.
    """
    try:
        stats = await job_manager.get_job_statistics()
        return stats

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
