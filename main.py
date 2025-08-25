import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import extraction, health, usage
from app.services.job_manager import initialize_job_manager, cleanup_job_manager
from app.services.usage_tracker import initialize_usage_tracker, cleanup_usage_tracker
from app.core.exceptions import TenderExtractionException, map_to_http_exception

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Tender Document Extraction Service...")
    
    # Initialize services
    try:
        await initialize_job_manager()
        logger.info("Job manager initialized successfully")
        
        await initialize_usage_tracker()
        logger.info("Usage tracker initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down Tender Document Extraction Service...")
    try:
        await cleanup_job_manager()
        logger.info("Job manager cleanup completed")
        
        await cleanup_usage_tracker()
        logger.info("Usage tracker cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


# Create FastAPI application
app = FastAPI(
    title="Tender Document Extraction Service",
    description="""
    AI-powered document extraction service using Google Gemini 2.5 Pro for 
    intelligent processing of tender documents and procurement notices.
    
    ## Features
    
    * **Multi-modal Analysis**: Process text, images, tables, and charts
    * **Structured Output**: Extract key tender information with confidence scores
    * **Batch Processing**: Handle multiple documents with progress tracking
    * **Prompt Engineering**: Centralized template system for optimal extraction
    * **Rate Limiting**: Intelligent API usage management
    * **Quality Assurance**: Confidence scoring and validation
    
    ## Authentication
    
    API key authentication required for production use.
    
    ## Rate Limits
    
    - Single document: Up to 60 requests per minute
    - Batch processing: Up to 10 batches per minute
    - File size limit: 50MB per document
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)

# Add CORS middleware
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )


# Exception handlers
@app.exception_handler(TenderExtractionException)
async def tender_exception_handler(request, exc: TenderExtractionException):
    """Handle custom tender extraction exceptions."""
    http_exc = map_to_http_exception(exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=http_exc.detail,
        headers=http_exc.headers
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    if settings.is_development:
        # In development, return detailed error information
        return JSONResponse(
            status_code=500,
            content={
                "message": "Internal server error",
                "error": str(exc),
                "type": type(exc).__name__
            }
        )
    else:
        # In production, return generic error message
        return JSONResponse(
            status_code=500,
            content={"message": "Internal server error"}
        )


# Include routers
app.include_router(health.router)
app.include_router(extraction.router)
app.include_router(usage.router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "name": "Tender Document Extraction Service",
        "version": "1.0.0",
        "description": "AI-powered document extraction using Google Gemini 2.5 Pro",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "detailed_health": "/health/detailed", 
            "api_docs": "/docs",
            "extraction": "/api/v1/extract",
            "batch_extraction": "/api/v1/extract/batch",
            "jobs": "/api/v1/jobs",
            "usage": "/api/v1/usage",
            "cost_analysis": "/api/v1/usage/cost-analysis"
        },
        "supported_formats": ["PDF", "DOCX", "TXT", "Images"],
        "features": [
            "Multi-modal document analysis",
            "Structured data extraction",
            "Batch processing with progress tracking",
            "Confidence scoring and quality assessment",
            "Rate limiting and cost optimization"
        ]
    }
