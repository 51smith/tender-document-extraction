"""Web interface router for Phase 3 enterprise features."""

import logging
from typing import Optional
from fastapi import APIRouter, Request, Form, File, UploadFile, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize templates
template_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

router = APIRouter(
    prefix="/web",
    tags=["Web Interface"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard with upload interface and job status."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Tender Document Extraction",
        "api_base": "http://localhost:8000",
    })


@router.get("/upload", response_class=HTMLResponse) 
async def upload_page(request: Request):
    """Document upload interface."""
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "title": "Upload Documents",
        "max_file_size": settings.max_file_size,
        "supported_formats": ["PDF", "DOCX", "TXT", "Images"],
    })


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request):
    """Jobs management and monitoring page."""
    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "title": "Job Management",
    })


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Advanced analytics dashboard."""
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "title": "Analytics Dashboard",
    })


@router.get("/webhooks", response_class=HTMLResponse)
async def webhooks_page(request: Request):
    """Webhook configuration interface."""
    return templates.TemplateResponse("webhooks.html", {
        "request": request,
        "title": "Webhook Configuration",
    })


@router.get("/job/{job_id}", response_class=HTMLResponse)
async def job_detail_page(request: Request, job_id: str):
    """Individual job details and results page."""
    return templates.TemplateResponse("job_detail.html", {
        "request": request,
        "title": f"Job {job_id}",
        "job_id": job_id,
    })