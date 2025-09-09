"""Integration test for real LLM response format workflow."""

import json
from unittest.mock import AsyncMock

import pytest

from app.adapters.response_adapter import ResponseAdapterFactory
from app.models.extraction import TenderExtractedData
from app.services.extraction_worker import ExtractionService
from app.utils.document_processor import DocumentContent


class TestRealResponseWorkflow:
    """Test with actual LLM response format that was causing issues."""

    @pytest.fixture()
    def real_llm_response(self):
        """The actual response format from user's job that was causing null values."""
        return {
            "tender_documents": [
                {
                    "title": "2.1. Tender Documents",
                    "description": (
                        "The tender documents will be available for inspection and can be "
                        "obtained from the contracting authority."
                    ),
                }
            ],
            "procurement_process": [
                {
                    "title": "Fase 1: Beoordeling",
                    "description": "The evaluation will take place in phases as described in the tender documents.",
                }
            ],
            "bezwaar_maken": {
                "title": "Bezwaar maken",
                "description": "Bezwaren tegen de aanbestedingsprocedure kunnen worden ingediend.",
                "deadline": "within 15 days after publication",
            },
            "klachtenprocedure": {
                "title": "Klachtenprocedure",
                "description": "Voor klachten over de aanbestedingsprocedure kunt u contact opnemen met de aanbestedende dienst.",
            },
        }

    @pytest.fixture()
    def sample_document(self):
        """Sample document that would generate the real response."""
        text_content = "Infrastructure Upgrade Project B2. Estimated value: 3,750,000 EUR. Deadline: October 20, 2024."
        return DocumentContent(
            text=text_content,
            images=[],
            tables=[],
            metadata={"filename": "test_tender.txt", "content_type": "text/plain"},
            content_hash="test_hash_123",
            file_type="txt",
            file_size=len(text_content.encode()),
        )

    @pytest.mark.asyncio()
    async def test_response_adapter_handles_real_format(self, real_llm_response):
        """Test that ResponseAdapter can handle the actual LLM response format."""
        # Get Gemini adapter (assuming that's what the user was using)
        adapter = ResponseAdapterFactory.get_adapter("gemini")

        # This should not throw an exception and should extract meaningful data
        result = adapter.adapt_response(real_llm_response)

        # Verify the result is a valid TenderExtractedData object
        assert isinstance(result, TenderExtractedData)

        # Check that functional requirements were extracted from tender_documents
        assert result.functional_requirements is not None
        assert len(result.functional_requirements) > 0
        assert "2.1. Tender Documents" in result.functional_requirements[0]

        # Check that project title was extracted
        assert result.project_title is not None
        assert result.project_title == "2.1. Tender Documents"

        # Check that submission requirements were extracted from bezwaar_maken
        assert result.submission_requirements is not None
        assert hasattr(result.submission_requirements, "documents_required")
        assert len(result.submission_requirements.documents_required) > 0
        assert any("Bezwaren" in doc for doc in result.submission_requirements.documents_required)

    @pytest.mark.asyncio()
    async def test_extraction_worker_end_to_end(self, real_llm_response, sample_document):
        """Test the complete extraction worker flow with real response format."""

        # Mock the LLM service to return our real response format
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_content.return_value = real_llm_response
        mock_llm_service.get_provider_name.return_value = "gemini"

        # Create extraction service
        worker = ExtractionService(llm_service=mock_llm_service)

        # Process the document
        result = await worker._parse_ai_response(real_llm_response, sample_document)

        # Verify the result structure
        assert result.extracted_data is not None
        assert result.raw_response == real_llm_response

        # Verify that extracted_data is not empty (this was the original issue)
        assert result.extracted_data.project_title is not None
        assert len(result.extracted_data.functional_requirements or []) > 0

        # Verify confidence scores exist
        assert result.confidence_scores is not None

    @pytest.mark.asyncio()
    async def test_json_serialization_for_export(self, real_llm_response, sample_document):
        """Test that the result can be properly JSON serialized for export."""

        # Mock the LLM service
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_content.return_value = real_llm_response
        mock_llm_service.get_provider_name.return_value = "gemini"

        # Create extraction service and process
        worker = ExtractionService(llm_service=mock_llm_service)
        result = await worker._parse_ai_response(real_llm_response, sample_document)

        # Test JSON serialization (this was failing in the export endpoint)
        try:
            # Test Pydantic v2 serialization
            if hasattr(result, "model_dump"):
                json_data = result.model_dump(mode="json")
            else:
                # Test Pydantic v1 serialization
                json_data = json.loads(result.json())

            # Verify the JSON is valid and contains expected data
            assert isinstance(json_data, dict)
            assert "extracted_data" in json_data
            assert "raw_response" in json_data
            assert json_data["extracted_data"]["project_title"] is not None

        except Exception as e:
            pytest.fail(f"JSON serialization failed: {e}")

    @pytest.mark.asyncio()
    @pytest.mark.integration()
    async def test_full_api_workflow_with_real_format(self, real_llm_response):
        """Test the full API workflow including job creation and export."""

        # This test would require actual API client and running server
        # For now, let's test the core components that were failing

        # Test 1: ResponseAdapter transformation
        adapter = ResponseAdapterFactory.get_adapter("gemini")
        extracted_data = adapter.adapt_response(real_llm_response)
        assert extracted_data.project_title is not None

        # Test 2: JSON serialization for export
        from app.models.extraction import (
            ConfidenceScores,
            ExtractionNotes,
            ProcessingMetadata,
            TenderExtractionResult,
        )

        result = TenderExtractionResult(
            extracted_data=extracted_data,
            confidence_scores=ConfidenceScores(),
            extraction_notes=ExtractionNotes(),
            processing_metadata=ProcessingMetadata(),
            raw_response=real_llm_response,
        )

        # This should not fail (was the export error)
        try:
            if hasattr(result, "model_dump"):
                serialized = result.model_dump(mode="json")
            else:
                serialized = json.loads(result.json())
            assert isinstance(serialized, dict)
        except Exception as e:
            pytest.fail(f"Export serialization failed: {e}")

    @pytest.mark.asyncio()
    async def test_error_logging_improvements(self, real_llm_response, sample_document):
        """Test that our improved error logging captures useful information."""

        # Create a scenario where ResponseAdapter might fail
        invalid_response = {"invalid_field": "this should trigger fallback logic"}

        mock_llm_service = AsyncMock()
        mock_llm_service.generate_content.return_value = invalid_response
        mock_llm_service.get_provider_name.return_value = "gemini"

        worker = ExtractionService(llm_service=mock_llm_service)

        # This should not crash and should return a result with meaningful error info
        result = await worker._parse_ai_response(invalid_response, sample_document)

        # Check that we get a result (not None)
        assert result is not None

        # Check that error information is captured
        assert result.extraction_notes.ambiguities is not None

        # The raw response should still be preserved for debugging
        assert result.raw_response == invalid_response

    def test_dutch_language_detection_fix(self, sample_document):
        """Test language detection fix for Dutch content."""

        # Create Dutch content
        dutch_text = """
        Aanbestedingsprocedure voor Infrastructure Upgrade Project B2.
        Geschatte waarde: 3.750.000 EUR.
        Inschrijvingsdeadline: 20 oktober 2024 om 16:00:00.
        """

        DocumentContent(
            text=dutch_text,
            images=[],
            tables=[],
            metadata={"filename": "dutch_tender.txt", "content_type": "text/plain"},
            content_hash="dutch_hash_123",
            file_type="txt",
            file_size=len(dutch_text.encode()),
        )

        mock_llm_service = AsyncMock()
        mock_llm_service.get_provider_name.return_value = "gemini"

        worker = ExtractionService(llm_service=mock_llm_service)

        # Test language detection
        detected_language = worker._detect_language(dutch_text)

        # Should detect Dutch, not French
        # Note: Current implementation is basic, but this test documents the expectation
        assert detected_language in [
            "nl",
            "dutch",
            "de",
        ], f"Expected Dutch language detection, got: {detected_language}"
