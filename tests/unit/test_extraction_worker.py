"""
Comprehensive tests for the ExtractionWorker service.
Testing coverage target: 0% → 85%
"""

import asyncio
import json
import logging
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    DocumentProcessingError,
    GeminiAPIException,
    TenderExtractionException,
)
from app.models.extraction import (
    BatchExtractionRequest,
    ConfidenceScores,
    ContractType,
    DocumentExtractionRequest,
    ExtractionComplexity,
    ExtractionNotes,
    ExtractionStatus,
    ProcessingMetadata,
    TenderExtractedData,
    TenderExtractionResult,
)
from app.services.extraction_worker import ExtractionService, process_extraction_job
from app.utils.document_processor import DocumentContent


class TestExtractionService:
    """Test ExtractionService class functionality."""

    @pytest.fixture()
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all service dependencies."""
        with patch("app.services.extraction_worker.get_llm_service") as mock_llm, patch(
            "app.services.extraction_worker.get_document_processor"
        ) as mock_doc_proc, patch(
            "app.services.extraction_worker.get_prompt_builder"
        ) as mock_prompt, patch(
            "app.services.extraction_worker.get_job_manager"
        ) as mock_job_mgr, patch(
            "app.services.extraction_worker.get_gemini_client"
        ) as mock_gemini:
            # Setup LLM service mock
            mock_llm_instance = MagicMock()
            mock_llm_instance.get_provider_name.return_value = "openai"
            mock_llm_instance.model = "gpt-4"
            mock_llm_instance.get_provider_info.return_value = {
                "provider": "openai",
                "model": "gpt-4",
            }
            mock_llm_instance.generate_content = AsyncMock()
            mock_llm.return_value = mock_llm_instance

            # Setup document processor mock (synchronous methods)
            mock_doc_proc_instance = MagicMock()
            mock_doc_proc_instance.process_document = MagicMock()
            mock_doc_proc_instance.validate_document = MagicMock()
            mock_doc_proc_instance.get_multimodal_content = MagicMock()
            mock_doc_proc.return_value = mock_doc_proc_instance

            # Setup prompt builder mock
            mock_prompt_instance = MagicMock()
            mock_prompt.return_value = mock_prompt_instance

            # Setup job manager mock
            mock_job_mgr_instance = AsyncMock()
            mock_job_mgr.return_value = mock_job_mgr_instance

            # Setup Gemini client mock
            mock_gemini_instance = AsyncMock()
            mock_gemini_instance.generate_content = AsyncMock()
            mock_gemini_instance.process_multiple_documents = AsyncMock()
            mock_gemini_instance.upload_file = AsyncMock()
            mock_gemini_instance.list_files = AsyncMock()
            mock_gemini_instance.delete_file = AsyncMock()
            mock_gemini.return_value = mock_gemini_instance

            yield {
                "llm_service": mock_llm_instance,
                "document_processor": mock_doc_proc_instance,
                "prompt_builder": mock_prompt_instance,
                "job_manager": mock_job_mgr_instance,
                "gemini_client": mock_gemini_instance,
            }

    @pytest.fixture()
    @pytest.fixture
    def mock_document_content(self):
        """Create mock document content."""
        return DocumentContent(
            text="Sample tender document content",
            images=[],
            tables=[],
            metadata={"page_count": 1, "word_count": 4},
            content_hash="test_hash",
            file_type="application/pdf",
            file_size=1000,
        )

    @pytest.fixture()
    @pytest.fixture
    def mock_extraction_request(self):
        """Create mock extraction request."""
        return DocumentExtractionRequest(
            filename="test.pdf",
            content_type="application/pdf",
            config_name="default",
            enable_multimodal=False,
        )

    def test_extraction_service_initialization_gemini_provider(self, mock_dependencies):
        """Test ExtractionService initialization with Gemini provider."""
        # Configure as Gemini provider
        mock_dependencies["llm_service"].get_provider_name.return_value = "gemini"

        service = ExtractionService()

        assert service.llm_service is not None
        assert service.document_processor is not None
        assert service.prompt_builder is not None
        assert service.job_manager is not None
        assert service.gemini_client is not None

    def test_extraction_service_initialization_non_gemini_provider(self, mock_dependencies):
        """Test ExtractionService initialization with non-Gemini provider."""
        # Configure as OpenAI provider (default in fixture)
        service = ExtractionService()

        assert service.llm_service is not None
        assert service.document_processor is not None
        assert service.prompt_builder is not None
        assert service.job_manager is not None
        assert service.gemini_client is None

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_process_document_content_success(
        self, mock_dependencies, mock_document_content, mock_extraction_request
    ):
        """Test successful document content processing."""
        # Setup mocks
        mock_dependencies[
            "document_processor"
        ].process_document.return_value = mock_document_content
        mock_dependencies["document_processor"].validate_document.return_value = {
            "is_valid": True,
            "errors": [],
        }
        mock_dependencies["prompt_builder"].build_prompt.return_value = {
            "prompt": "Extract tender information from: Sample tender document content"
        }

        # Mock LLM response
        mock_ai_response = {
            "response": json.dumps(
                {
                    "extracted_data": {"project_title": "Test Project", "contract_type": "works"},
                    "confidence_scores": {"project_title": 0.9, "overall": 0.85},
                }
            )
        }
        mock_dependencies["llm_service"].generate_content = AsyncMock(return_value=mock_ai_response)

        service = ExtractionService()
        result = await service._process_document_content(b"test content", mock_extraction_request)

        assert isinstance(result, TenderExtractionResult)
        assert result.extracted_data.project_title == "Test Project"
        assert result.confidence_scores.overall == 0.85
        assert result.processing_metadata.processing_time > 0

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_process_document_content_with_validation_error(
        self, mock_dependencies, mock_document_content, mock_extraction_request
    ):
        """Test document processing with validation failure."""
        # Setup validation failure
        mock_dependencies[
            "document_processor"
        ].process_document.return_value = mock_document_content
        mock_dependencies["document_processor"].validate_document.return_value = {
            "is_valid": False,
            "errors": ["Document is too small", "Missing required content"],
        }

        service = ExtractionService()

        result = await service._process_document_content(
            b"invalid content", mock_extraction_request
        )

        # The method catches DocumentProcessingError and returns a partial result
        assert isinstance(result, TenderExtractionResult)
        assert "Document validation failed" in result.extraction_notes.ambiguities[0]

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_process_document_content_with_multimodal_gemini(
        self, mock_dependencies, mock_extraction_request
    ):
        """Test multimodal processing with Gemini client."""
        # Setup as Gemini provider
        mock_dependencies["llm_service"].get_provider_name.return_value = "gemini"

        # Setup document with images
        mock_doc_with_images = DocumentContent(
            text="Sample content",
            images=[{"data": b"fake_image", "mime_type": "image/jpeg"}],
            tables=[],
            metadata={"page_count": 1},
            content_hash="test_hash",
            file_type="application/pdf",
            file_size=1000,
        )

        mock_dependencies["document_processor"].process_document.return_value = mock_doc_with_images
        mock_dependencies["document_processor"].validate_document.return_value = {
            "is_valid": True,
            "errors": [],
        }
        mock_dependencies["document_processor"].get_multimodal_content.return_value = [
            "Sample content",
            {"mime_type": "image/jpeg", "data": b"fake_image"},
        ]
        mock_dependencies["prompt_builder"].build_prompt.return_value = {
            "prompt": "Extract from multimodal content"
        }

        # Mock Gemini response
        mock_gemini_response = {
            "extracted_data": {"project_title": "Multimodal Project", "contract_type": "works"},
            "confidence_scores": {"project_title": 0.95, "overall": 0.9},
        }
        mock_dependencies["gemini_client"].generate_content.return_value = mock_gemini_response

        # Enable multimodal
        mock_extraction_request.enable_multimodal = True

        service = ExtractionService()
        service.gemini_client = mock_dependencies["gemini_client"]  # Manually set for test

        result = await service._process_document_content(b"test content", mock_extraction_request)

        assert result.extracted_data.project_title == "Multimodal Project"
        mock_dependencies["gemini_client"].generate_content.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_process_document_content_multimodal_fallback(
        self, mock_dependencies, mock_extraction_request
    ):
        """Test multimodal content fallback to text-only for non-Gemini providers."""
        # Setup document with images but non-Gemini provider
        mock_doc_with_images = DocumentContent(
            text="Sample content",
            images=[{"data": b"fake_image", "mime_type": "image/jpeg"}],
            tables=[],
            metadata={"page_count": 1},
            content_hash="test_hash",
            file_type="application/pdf",
            file_size=1000,
        )

        mock_dependencies["document_processor"].process_document.return_value = mock_doc_with_images
        mock_dependencies["document_processor"].validate_document.return_value = {
            "is_valid": True,
            "errors": [],
        }
        mock_dependencies["prompt_builder"].build_prompt.return_value = {
            "prompt": "Extract from text content"
        }

        # Mock LLM response
        mock_ai_response = {
            "response": json.dumps({"extracted_data": {"project_title": "Text-only Project"}})
        }
        mock_dependencies["llm_service"].generate_content = AsyncMock(return_value=mock_ai_response)

        # Enable multimodal but with non-Gemini provider
        mock_extraction_request.enable_multimodal = True

        service = ExtractionService()
        result = await service._process_document_content(b"test content", mock_extraction_request)

        assert result.extracted_data.project_title == "Text-only Project"
        # Should use LLM service, not Gemini client
        mock_dependencies["llm_service"].generate_content.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_process_document_content_extraction_error(
        self, mock_dependencies, mock_document_content, mock_extraction_request
    ):
        """Test handling of extraction errors."""
        # Setup mocks for normal processing
        mock_dependencies[
            "document_processor"
        ].process_document.return_value = mock_document_content
        mock_dependencies["document_processor"].validate_document.return_value = {
            "is_valid": True,
            "errors": [],
        }
        mock_dependencies["prompt_builder"].build_prompt.return_value = {
            "prompt": "Extract tender information"
        }

        # Make LLM service raise an error
        mock_dependencies["llm_service"].generate_content = AsyncMock(
            side_effect=GeminiAPIException("API Error")
        )

        service = ExtractionService()
        result = await service._process_document_content(b"test content", mock_extraction_request)

        # Should return partial result with error
        assert isinstance(result, TenderExtractionResult)
        assert "API Error" in result.raw_response["error"]
        assert result.raw_response["type"] == "GeminiAPIException"
        assert "Extraction failed" in result.extraction_notes.ambiguities[0]

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_process_multiple_documents_gemini_path(self, mock_dependencies):
        """Test multiple document processing with Gemini File API."""
        # Setup as Gemini provider
        mock_dependencies["llm_service"].get_provider_name.return_value = "gemini"

        documents = {"doc1.pdf": b"Content 1", "doc2.pdf": b"Content 2"}

        batch_request = BatchExtractionRequest(
            documents=[
                DocumentExtractionRequest(filename="doc1.pdf", config_name="default"),
                DocumentExtractionRequest(filename="doc2.pdf", config_name="default"),
            ]
        )

        mock_dependencies["prompt_builder"].build_prompt.return_value = {
            "prompt": "Multi-document extraction prompt"
        }

        # Mock Gemini multi-document response
        mock_gemini_response = {
            "extracted_data": {"project_title": "Combined Project"},
            "confidence_scores": {"project_title": 0.9, "overall": 0.85},
        }
        mock_dependencies["gemini_client"].process_multiple_documents = AsyncMock(
            return_value=mock_gemini_response
        )

        # Process documents as combined text (fallback path)
        mock_doc_content = DocumentContent(
            text="Processed document text",
            images=[],
            tables=[],
            metadata={},
            content_hash="hash",
            file_type="application/pdf",
            file_size=1000,
        )
        mock_dependencies["document_processor"].process_document.return_value = mock_doc_content
        mock_dependencies["document_processor"].validate_document.return_value = {
            "is_valid": True,
            "errors": [],
        }

        # Mock LLM response with proper async handling
        mock_ai_response = {
            "response": json.dumps({"extracted_data": {"project_title": "Combined Project"}})
        }
        mock_dependencies["llm_service"].generate_content = AsyncMock(return_value=mock_ai_response)

        service = ExtractionService()
        service.gemini_client = mock_dependencies["gemini_client"]  # Manually set for test
        result = await service._process_multiple_documents(documents, batch_request)

        assert result.extracted_data.project_title == "Combined Project"
        # Should use Gemini path since gemini_client is available
        mock_dependencies["gemini_client"].process_multiple_documents.assert_called_once()

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_process_multiple_documents_non_gemini_path(self, mock_dependencies):
        """Test multiple document processing with non-Gemini provider."""
        documents = {"doc1.pdf": b"Content 1", "doc2.pdf": b"Content 2"}

        batch_request = BatchExtractionRequest(
            documents=[
                DocumentExtractionRequest(filename="doc1.pdf", config_name="default"),
                DocumentExtractionRequest(filename="doc2.pdf", config_name="default"),
            ]
        )

        # Mock document processing for each document
        mock_doc_content = DocumentContent(
            text="Processed document text",
            images=[],
            tables=[],
            metadata={},
            content_hash="hash",
            file_type="application/pdf",
            file_size=1000,
        )
        mock_dependencies["document_processor"].process_document.return_value = mock_doc_content
        mock_dependencies["document_processor"].validate_document.return_value = {
            "is_valid": True,
            "errors": [],
        }
        mock_dependencies["prompt_builder"].build_prompt.return_value = {
            "prompt": "Multi-document extraction prompt"
        }

        # Mock LLM response with proper async handling
        mock_ai_response = {
            "response": json.dumps({"extracted_data": {"project_title": "Combined Project"}})
        }
        mock_dependencies["llm_service"].generate_content = AsyncMock(return_value=mock_ai_response)

        service = ExtractionService()
        result = await service._process_multiple_documents(documents, batch_request)

        assert result.extracted_data.project_title == "Combined Project"
        # Should call document processor for each document
        # Note: call_count might be higher due to initialization calls
        assert mock_dependencies["document_processor"].process_document.call_count >= 2

    @pytest.mark.asyncio()
    async def test_parse_ai_response_full_format(self):
    def test_parse_ai_response_full_format(self):
        """Test parsing AI response in full expected format."""
        service = ExtractionService()

        mock_document = DocumentContent(
            text="Test content",
            images=[],
            tables=[],
            metadata={},
            content_hash="hash",
            file_type="application/pdf",
            file_size=1000,
        )

        ai_response = {
            "extracted_data": {"project_title": "Test Project", "contract_type": "works"},
            "confidence_scores": {"project_title": 0.9, "overall": 0.85},
            "extraction_notes": {
                "ambiguities": ["Some ambiguity"],
                "assumptions": ["Some assumption"],
            },
            "processing_metadata": {"model": "test-model"},
            "_metadata": {"model": "gpt-4", "actual_tokens": 1200, "timestamp": 1234567890.0},
        }

        result = await service._parse_ai_response(ai_response, mock_document)
        result = service._parse_ai_response(ai_response, mock_document)

        assert result.extracted_data.project_title == "Test Project"
        assert result.extracted_data.contract_type == ContractType.WORKS
        assert result.confidence_scores.overall == 0.85
        assert "Some ambiguity" in result.extraction_notes.ambiguities
        assert result.processing_metadata.actual_tokens == 1200
        assert result.processing_metadata.document_type == "application/pdf"

    @pytest.mark.asyncio()
    async def test_parse_ai_response_minimal_format(self):
    def test_parse_ai_response_minimal_format(self):
        """Test parsing AI response in minimal format."""
        service = ExtractionService()

        mock_document = DocumentContent(
            text="Test content",
            images=[],
            tables=[],
            metadata={},
            content_hash="hash",
            file_type="text/plain",
            file_size=500,
        )

        ai_response = {"project_title": "Simple Project", "contract_type": "supply"}

        result = await service._parse_ai_response(ai_response, mock_document)
        result = service._parse_ai_response(ai_response, mock_document)

        assert result.extracted_data.project_title == "Simple Project"
        assert result.extracted_data.contract_type == ContractType.SUPPLY
        assert result.processing_metadata.document_type == "text/plain"

    @pytest.mark.asyncio()
    async def test_parse_ai_response_with_error(self):
    def test_parse_ai_response_with_error(self):
        """Test parsing AI response that causes parsing error."""
        service = ExtractionService()

        mock_document = DocumentContent(
            text="Test content",
            images=[],
            tables=[],
            metadata={},
            content_hash="hash",
            file_type="application/pdf",
            file_size=1000,
        )

        # Invalid response that will cause parsing error (non-serializable)
        class BadObject:
            def __str__(self):
                raise ValueError("Cannot serialize this object")

        ai_response = {
            "extracted_data": {
                "project_title": BadObject(),  # This will cause adapter to fail
            }
        }

        result = await service._parse_ai_response(ai_response, mock_document)
        # Invalid response that will cause parsing error
        ai_response = {
            "extracted_data": {
                "invalid_field": "invalid_value",
                "contract_type": "invalid_contract_type",
            }
        }

        result = service._parse_ai_response(ai_response, mock_document)

        # Should return minimal result with error
        assert isinstance(result.extracted_data, TenderExtractedData)
        assert "Failed to parse AI response" in result.extraction_notes.ambiguities[0]
        assert result.processing_metadata.extraction_complexity == ExtractionComplexity.COMPLEX

    def test_detect_language_english(self):
        """Test language detection for English text."""
        service = ExtractionService()

        english_text = "This is a tender for the construction project with contract specifications."
        result = service._detect_language(english_text)

        assert result == "en"

    def test_detect_language_german(self):
        """Test language detection for German text."""
        service = ExtractionService()

        german_text = "Das ist eine Ausschreibung für das Bauprojekt mit der Vertragsspezifikation."
        result = service._detect_language(german_text)

        assert result == "de"

    def test_detect_language_unknown(self):
        """Test language detection for unknown/ambiguous text."""
        service = ExtractionService()

        unknown_text = "Lorem ipsum dolor sit amet consectetur."
        result = service._detect_language(unknown_text)

        assert result == "unknown"

    def test_detect_language_empty(self):
        """Test language detection for empty text."""
        service = ExtractionService()

        result = service._detect_language("")

        assert result == "unknown"

    def test_assess_complexity_simple(self):
        """Test complexity assessment for simple documents."""
        service = ExtractionService()

        simple_doc = DocumentContent(
            text="A" * 1000,  # Short text
            images=[],
            tables=[],
            metadata={"page_count": 1},
            content_hash="hash",
            file_type="text/plain",
            file_size=1000,
        )

        simple_response = {"extracted_data": {"project_title": "Simple"}}

        result = service._assess_complexity(simple_doc, simple_response)

        assert result == ExtractionComplexity.SIMPLE

    def test_assess_complexity_complex(self):
        """Test complexity assessment for complex documents."""
        service = ExtractionService()

        # Create a complex document scenario that will trigger high complexity score
        complex_doc = DocumentContent(
            text="A" * 100000,  # Long text (>50k chars = +2 complexity)
            images=[{"data": b"img1"}, {"data": b"img2"}],  # Images = +1 complexity
            tables=[{"data": f"table{i}"} for i in range(10)],  # >5 tables = +1 complexity
            metadata={"page_count": 50},
            content_hash="hash",
            file_type="application/pdf",
            file_size=100000,
        )

        # Response with ambiguities and missing info = +2 complexity
        complex_response = {
            "extracted_data": {
                "project_title": "Complex",
                "evaluation_criteria": [{"criterion": "Price"}, {"criterion": "Quality"}],
            },
            "extraction_notes": {
                "ambiguities": ["Ambiguity 1", "Ambiguity 2"],  # +1 complexity
                "missing_information": ["Missing info"],  # +1 complexity
            },
            "_metadata": {"processing_time": 70},  # >60s = +2 complexity
        }

        # Total: 2 + 1 + 1 + 1 + 1 + 2 = 8 complexity points (>=5 = COMPLEX)
        result = service._assess_complexity(complex_doc, complex_response)

        assert result == ExtractionComplexity.COMPLEX


class TestWorkerFunctions:
    """Test standalone worker functions."""

    @pytest.mark.asyncio()
    @pytest.mark.asyncio
    async def test_process_job_async_batch_request(self):
        """Test async job processing for batch requests."""
        from app.services.extraction_worker import _process_job_async

        job_id = "test-job-123"
        request_data = {
            "documents": [
                {"filename": "doc1.pdf", "config_name": "default"},
                {"filename": "doc2.pdf", "config_name": "default"},
            ]
        }

        with patch("app.services.extraction_worker.ExtractionService") as mock_service_class, patch(
            "app.services.job_manager.JobManager"
        ) as mock_job_manager_class, patch(
            "app.services.extraction_worker.BatchExtractionRequest"
        ) as mock_batch_req:
            # Setup mocks
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_job_manager = AsyncMock()
            mock_job_manager.get_file_contents.return_value = {
                "doc1.pdf": b"content1",
                "doc2.pdf": b"content2",
            }
            mock_job_manager_class.return_value = mock_job_manager

            mock_batch_request = MagicMock()
            mock_batch_request.documents = [
                MagicMock(filename="doc1.pdf"),
                MagicMock(filename="doc2.pdf"),
            ]
            mock_batch_req.return_value = mock_batch_request

            # Mock successful extraction
            mock_result = TenderExtractionResult(
                extracted_data=TenderExtractedData(project_title="Test"),
                confidence_scores=ConfidenceScores(),
                extraction_notes=ExtractionNotes(),
                processing_metadata=ProcessingMetadata(),
            )
            mock_service._process_multiple_documents.return_value = mock_result

            await _process_job_async(job_id, request_data)
            result = await _process_job_async(job_id, request_data)

            # Verify job manager was initialized and used
            mock_job_manager.initialize.assert_called_once()
            mock_job_manager.get_file_contents.assert_called_once_with(job_id)
            mock_job_manager.update_job_status.assert_called()
            mock_service._process_multiple_documents.assert_called_once()

    def test_process_extraction_job_success(self):
        """Test successful extraction job processing."""
        job_id = "test-job-123"
        request_data = {"test": "data"}

        with patch("app.services.extraction_worker._process_job_async") as mock_async_process:
            mock_async_process.return_value = {"result": "success"}

            with patch("asyncio.new_event_loop") as mock_new_loop, patch("asyncio.set_event_loop"):
            with patch("asyncio.new_event_loop") as mock_new_loop, patch(
                "asyncio.set_event_loop"
            ) as mock_set_loop:
                mock_loop = MagicMock()
                mock_new_loop.return_value = mock_loop
                mock_loop.run_until_complete.return_value = {"result": "success"}
                mock_loop.is_running.return_value = False
                mock_loop.is_closed.return_value = False

                result = process_extraction_job(job_id, request_data)

                assert result == {"result": "success"}
                mock_loop.run_until_complete.assert_called_once()
                mock_loop.close.assert_called_once()

    def test_process_extraction_job_with_error(self):
        """Test extraction job processing with error."""
        job_id = "test-job-123"
        request_data = {"test": "data"}

        with patch(
            "app.services.extraction_worker._process_job_async"
        ) as mock_async_process, patch("app.services.extraction_worker._handle_job_error"):
            # Make async process raise an error
            mock_async_process.side_effect = Exception("Processing failed")

            with patch("asyncio.new_event_loop") as mock_new_loop, patch("asyncio.set_event_loop"):
        ) as mock_async_process, patch(
            "app.services.extraction_worker._handle_job_error"
        ) as mock_handle_error:
            # Make async process raise an error
            mock_async_process.side_effect = Exception("Processing failed")

            with patch("asyncio.new_event_loop") as mock_new_loop, patch(
                "asyncio.set_event_loop"
            ) as mock_set_loop:
                mock_loop = MagicMock()
                mock_new_loop.return_value = mock_loop
                mock_loop.run_until_complete.side_effect = Exception("Processing failed")
                mock_loop.is_running.return_value = False
                mock_loop.is_closed.return_value = False

                with pytest.raises(Exception, match="Processing failed"):
                    process_extraction_job(job_id, request_data)
                mock_loop.close.assert_called_once()

    @pytest.mark.asyncio()
                with pytest.raises(Exception) as exc_info:
                    process_extraction_job(job_id, request_data)

                assert "Processing failed" in str(exc_info.value)
                mock_loop.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_job_error(self):
        """Test job error handling function."""
        from app.services.extraction_worker import _handle_job_error

        job_id = "test-job-123"
        error = Exception("Test error")

        with patch("app.services.job_manager.JobManager") as mock_job_manager_class:
            mock_job_manager = AsyncMock()
            mock_job_manager_class.return_value = mock_job_manager

            await _handle_job_error(job_id, error, None)

            # Verify error was handled
            mock_job_manager.initialize.assert_called_once()
            mock_job_manager.update_job_status.assert_called_with(
                job_id, ExtractionStatus.FAILED, error_message="Test error"
            )
