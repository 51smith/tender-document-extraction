import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.gemini_service import GeminiClient, get_gemini_client
from app.services.job_manager import JobManager, get_job_manager
from app.utils.prompt_builder import PromptBuilder, get_prompt_builder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.environment,
    }


@router.get("/health/detailed")
async def detailed_health_check(
    gemini_client: GeminiClient = Depends(get_gemini_client),
    job_manager: JobManager = Depends(get_job_manager),
    prompt_builder: PromptBuilder = Depends(get_prompt_builder),
):
    """
    Detailed health check including all service dependencies.
    """

    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.environment,
        "services": {},
    }

    overall_healthy = True

    # Check Gemini API
    try:
        gemini_test = await gemini_client.test_connection()
        health_status["services"]["gemini"] = {
            "status": "healthy" if gemini_test["status"] == "success" else "unhealthy",
            "details": gemini_test,
        }
        if gemini_test["status"] != "success":
            overall_healthy = False
    except Exception as e:
        health_status["services"]["gemini"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check Redis/Job Manager
    try:
        # Test Redis connection by getting statistics
        job_stats = await job_manager.get_job_statistics()
        health_status["services"]["redis"] = {"status": "healthy", "details": job_stats}
    except Exception as e:
        health_status["services"]["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check Prompt Builder
    try:
        available_templates = prompt_builder.get_available_templates()
        health_status["services"]["prompt_builder"] = {
            "status": "healthy",
            "available_templates": available_templates,
        }
    except Exception as e:
        health_status["services"]["prompt_builder"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Set overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"

    # Return appropriate HTTP status
    if overall_healthy:
        return health_status
    else:
        return JSONResponse(status_code=503, content=health_status)


@router.get("/health/gemini")
async def gemini_health_check(gemini_client: GeminiClient = Depends(get_gemini_client)):
    """
    Specific health check for Gemini API connectivity.
    """
    try:
        test_result = await gemini_client.test_connection()
        usage_stats = gemini_client.get_usage_stats()

        return {
            "status": "healthy" if test_result["status"] == "success" else "unhealthy",
            "connection_test": test_result,
            "usage_stats": usage_stats,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


@router.get("/health/redis")
async def redis_health_check(job_manager: JobManager = Depends(get_job_manager)):
    """
    Specific health check for Redis connectivity.
    """
    try:
        stats = await job_manager.get_job_statistics()

        return {
            "status": "healthy",
            "statistics": stats,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


@router.get("/ready")
async def readiness_check(
    gemini_client: GeminiClient = Depends(get_gemini_client),
    job_manager: JobManager = Depends(get_job_manager),
):
    """
    Kubernetes readiness probe endpoint.

    Returns 200 if the application is ready to serve requests.
    """
    try:
        # Quick check of critical dependencies

        # Test Gemini API with minimal request
        usage_stats = gemini_client.get_usage_stats()
        if not usage_stats:
            raise Exception("Gemini client not initialized")

        # Test Redis connection
        await job_manager.get_job_statistics()

        return {"status": "ready"}

    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe endpoint.

    Returns 200 if the application is alive (basic functionality works).
    """
    try:
        # Basic application liveness check
        current_time = datetime.utcnow()

        return {
            "status": "alive",
            "timestamp": current_time.isoformat(),
            "uptime_seconds": 0,  # This would be calculated from app start time
        }

    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not alive")
