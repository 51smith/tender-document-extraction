import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.config import settings
from app.services.gemini_service import reset_gemini_client
from app.services.job_manager import get_job_manager
from app.services.usage_tracker import get_usage_tracker
from app.utils.document_processor import reset_document_processor
from app.utils.prompt_builder import reset_prompt_builder

# Import app components
from main import app


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may require API keys)"
    )
    config.addinivalue_line("markers", "gemini_api: marks tests that call the real Gemini API")
    config.addinivalue_line("markers", "slow: marks tests as slow running")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def sample_pdf_content():
    """Mock PDF content for testing."""
    # Simple PDF header - in real tests you'd use a real PDF
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"


@pytest.fixture(scope="function")
def sample_text_content():
    """Sample text content for testing."""
    return """
    TENDER NOTICE

    Project: Highway Construction Project A1
    Contracting Authority: Department of Transportation
    Estimated Value: EUR 5,000,000 (excluding VAT)
    Submission Deadline: 2024-12-31T17:00:00Z

    REQUIREMENTS:
    - Highway construction experience
    - ISO 9001 certification
    - Minimum 10 years experience

    EVALUATION CRITERIA:
    - Price: 40%
    - Technical Quality: 35%
    - Experience: 25%
    """


@pytest.fixture(scope="function")
def sample_extraction_result():
    """Sample extraction result for testing."""
    from datetime import datetime
    from decimal import Decimal

    from app.models.extraction import (
        ConfidenceScores,
        ContractingAuthority,
        ContractType,
        EstimatedValue,
        EvaluationCriterion,
        ExtractionNotes,
        ProcessingMetadata,
        TenderExtractedData,
        TenderExtractionResult,
    )

    return TenderExtractionResult(
        extracted_data=TenderExtractedData(
            project_title="Highway Construction Project A1",
            contracting_authority=ContractingAuthority(name="Department of Transportation"),
            estimated_value=EstimatedValue(amount=Decimal("5000000"), currency="EUR"),
            contract_type=ContractType.WORKS,
            evaluation_criteria=[
                EvaluationCriterion(criterion="Price", weight_percentage=Decimal("40")),
                EvaluationCriterion(criterion="Technical Quality", weight_percentage=Decimal("35")),
                EvaluationCriterion(criterion="Experience", weight_percentage=Decimal("25")),
            ],
        ),
        confidence_scores=ConfidenceScores(
            project_title=0.95, contracting_authority=0.9, estimated_value=0.85, overall=0.9
        ),
        extraction_notes=ExtractionNotes(),
        processing_metadata=ProcessingMetadata(processing_time=2.5, model="gemini-2.5-pro"),
    )


@pytest.fixture(scope="function")
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "extracted_data": {
            "project_title": "Highway Construction Project A1",
            "contracting_authority": {"name": "Department of Transportation"},
            "estimated_value": {"amount": 5000000, "currency": "EUR"},
            "contract_type": "works",
        },
        "confidence_scores": {
            "project_title": 0.95,
            "contracting_authority": 0.9,
            "estimated_value": 0.85,
            "overall": 0.9,
        },
        "extraction_notes": {
            "ambiguities": [],
            "assumptions": [],
            "missing_information": [],
            "recommendations": [],
        },
        "processing_metadata": {
            "document_type": "application/pdf",
            "language": "en",
            "extraction_complexity": "moderate",
        },
        "_metadata": {
            "model": "gemini-2.5-pro",
            "processing_time": 2.5,
            "estimated_tokens": 1200,
            "actual_tokens": 1150,
            "timestamp": 1234567890.0,
        },
    }


@pytest.fixture(scope="function")
def mock_gemini_client(mock_gemini_response):
    """Mock Gemini client for testing."""
    mock_client = AsyncMock()
    mock_client.generate_content.return_value = mock_gemini_response
    mock_client.test_connection.return_value = {"status": "success", "model": "gemini-2.5-pro"}
    mock_client.get_usage_stats.return_value = {
        "rate_limits": {"available_requests": 100, "available_tokens": 50000}
    }
    return mock_client


@pytest.fixture(scope="function")
async def client():
    """FastAPI test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="function")
def sync_client():
    """Synchronous test client for simple tests."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    yield
    # Reset all singleton instances
    reset_gemini_client()
    reset_prompt_builder()
    reset_document_processor()


@pytest.fixture(scope="function")
async def mock_redis():
    """Mock Redis client for testing."""
    from unittest.mock import AsyncMock

    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    mock_redis.set.return_value = True
    mock_redis.get.return_value = None
    mock_redis.hgetall.return_value = {}
    mock_redis.zadd.return_value = 1
    mock_redis.zrange.return_value = []

    return mock_redis


@pytest.fixture(scope="function")
def prompt_validation_dataset():
    """Golden dataset for prompt validation."""
    return [
        {
            "document_text": """
            CALL FOR TENDERS
            Project: Software Development Services
            Authority: City Council IT Department
            Value: €250,000 (VAT included)
            Deadline: 2024-06-15 12:00 CET
            """,
            "expected_fields": {
                "project_title": "Software Development Services",
                "contracting_authority.name": "City Council IT Department",
                "estimated_value.amount": 250000,
                "estimated_value.currency": "EUR",
            },
            "complexity": "simple",
        },
        {
            "document_text": """
            PROCUREMENT NOTICE
            Ref: TND-2024-001
            
            Subject: Construction of New Bridge Infrastructure
            Procuring Entity: Ministry of Infrastructure
            Contact: John Smith (j.smith@infrastructure.gov)
            
            Project Details:
            - Bridge construction over River X
            - Expected duration: 18 months
            - Budget allocation: USD 12,500,000
            
            Submission Requirements:
            - Technical proposal
            - Financial proposal
            - Company certificates
            
            Evaluation Criteria:
            1. Technical approach (50%)
            2. Price competitiveness (30%) 
            3. Past experience (20%)
            
            Deadline: December 31, 2024 at 5:00 PM local time
            """,
            "expected_fields": {
                "project_title": "Construction of New Bridge Infrastructure",
                "contracting_authority.name": "Ministry of Infrastructure",
                "estimated_value.amount": 12500000,
                "estimated_value.currency": "USD",
                "evaluation_criteria": [
                    {"criterion": "Technical approach", "weight_percentage": 50},
                    {"criterion": "Price competitiveness", "weight_percentage": 30},
                    {"criterion": "Past experience", "weight_percentage": 20},
                ],
            },
            "complexity": "moderate",
        },
    ]


@pytest.fixture(scope="function")
def performance_test_data():
    """Data for performance testing."""
    return {
        "small_document": "A" * 1000,  # 1KB
        "medium_document": "B" * 10000,  # 10KB
        "large_document": "C" * 100000,  # 100KB
        "batch_documents": ["Doc" + str(i) * 1000 for i in range(10)],
    }


@pytest.fixture(scope="session")
def docker_compose_file():
    """Docker compose file for integration testing."""
    return os.path.join(os.path.dirname(__file__), "..", "docker-compose.test.yml")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add integration marker to tests with 'integration' in name
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Add slow marker to tests with 'slow' in name or that test performance
        if "slow" in item.nodeid or "performance" in item.nodeid:
            item.add_marker(pytest.mark.slow)

        # Add gemini_api marker to tests that use real API
        if "gemini_api" in item.nodeid or item.get_closest_marker("gemini_api"):
            item.add_marker(pytest.mark.gemini_api)


# Environment-specific fixtures
@pytest.fixture(scope="session")
def test_settings():
    """Override settings for testing."""
    original_settings = {
        "environment": settings.environment,
        "debug": settings.debug,
        "redis": settings.redis,
    }

    # Override for testing
    settings.environment = "test"
    settings.debug = True

    yield settings

    # Restore original settings
    for key, value in original_settings.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
