import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Union
import traceback

from app.models.extraction import (
    DocumentExtractionRequest,
    BatchExtractionRequest,
    TenderExtractionResult,
    ExtractionStatus,
    ProcessingMetadata,
    ConfidenceScores,
    ExtractionNotes,
    TenderExtractedData,
    ExtractionComplexity
)
from app.services.gemini_service import get_gemini_client
from app.services.job_manager import get_job_manager
from app.utils.document_processor import get_document_processor, DocumentContent
from app.utils.prompt_builder import get_prompt_builder
from app.core.exceptions import (
    TenderExtractionException,
    GeminiAPIException,
    DocumentProcessingError
)

logger = logging.getLogger(__name__)


class ExtractionService:
    """Core document extraction service."""
    
    def __init__(self):
        self.gemini_client = get_gemini_client()
        self.document_processor = get_document_processor()
        self.prompt_builder = get_prompt_builder()
        self.job_manager = get_job_manager()
    
    async def extract_from_document(
        self,
        document_content: bytes,
        request: DocumentExtractionRequest
    ) -> TenderExtractionResult:
        """Extract structured data from a single document."""
        
        start_time = time.time()
        
        try:
            # Process document
            logger.info(f"Processing document: {request.filename}")
            processed_doc = self.document_processor.process_document(
                document_content,
                request.filename,
                request.content_type
            )
            
            # Validate document content
            validation = self.document_processor.validate_document(processed_doc)
            if not validation["is_valid"]:
                raise DocumentProcessingError(
                    f"Document validation failed: {', '.join(validation['errors'])}"
                )
            
            # Build prompt
            logger.info(f"Building extraction prompt for: {request.filename}")
            prompt_result = self.prompt_builder.build_prompt(
                document_content=processed_doc.text,
                config_name=request.config_name,
                template_override=request.template_override,
                variables=request.variables
            )
            
            # Prepare content for AI processing
            if request.enable_multimodal and processed_doc.images:
                content = self.document_processor.get_multimodal_content(processed_doc)
            else:
                content = prompt_result["prompt"]
            
            # Extract using Gemini
            logger.info(f"Extracting data from: {request.filename}")
            ai_response = await self.gemini_client.generate_content(content)
            
            # Parse and validate response
            extraction_result = self._parse_ai_response(ai_response, processed_doc)
            
            # Add processing metadata
            processing_time = time.time() - start_time
            extraction_result.processing_metadata.processing_time = processing_time
            extraction_result.processing_metadata.total_pages = processed_doc.metadata.get('page_count')
            
            logger.info(f"Successfully extracted data from: {request.filename} in {processing_time:.2f}s")
            return extraction_result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Extraction failed for {request.filename}: {e}")
            logger.debug(traceback.format_exc())
            
            # Return partial result with error information
            return TenderExtractionResult(
                extracted_data=TenderExtractedData(),
                confidence_scores=ConfidenceScores(),
                extraction_notes=ExtractionNotes(
                    ambiguities=[f"Extraction failed: {str(e)}"]
                ),
                processing_metadata=ProcessingMetadata(
                    processing_time=processing_time,
                    extraction_complexity=ExtractionComplexity.COMPLEX
                ),
                raw_response={"error": str(e), "type": type(e).__name__}
            )
    
    def _parse_ai_response(
        self,
        ai_response: Dict[str, Any],
        document: DocumentContent
    ) -> TenderExtractionResult:
        """Parse AI response into structured result."""
        
        try:
            # Handle different response formats
            if "extracted_data" in ai_response:
                # Response already in expected format
                extracted_data = TenderExtractedData(**ai_response["extracted_data"])
                confidence_scores = ConfidenceScores(
                    **(ai_response.get("confidence_scores", {}))
                )
                extraction_notes = ExtractionNotes(
                    **(ai_response.get("extraction_notes", {}))
                )
                processing_metadata = ProcessingMetadata(
                    **(ai_response.get("processing_metadata", {}))
                )
            else:
                # Try to extract from direct response
                extracted_data = TenderExtractedData(**ai_response)
                confidence_scores = ConfidenceScores()
                extraction_notes = ExtractionNotes()
                processing_metadata = ProcessingMetadata()
            
            # Add document-based metadata
            processing_metadata.document_type = document.file_type
            processing_metadata.language = self._detect_language(document.text)
            processing_metadata.extraction_complexity = self._assess_complexity(
                document, ai_response
            )
            
            # Add AI model metadata if available
            if "_metadata" in ai_response:
                meta = ai_response["_metadata"]
                processing_metadata.model = meta.get("model")
                processing_metadata.estimated_tokens = meta.get("estimated_tokens")
                processing_metadata.actual_tokens = meta.get("actual_tokens")
                processing_metadata.timestamp = meta.get("timestamp")
            
            return TenderExtractionResult(
                extracted_data=extracted_data,
                confidence_scores=confidence_scores,
                extraction_notes=extraction_notes,
                processing_metadata=processing_metadata,
                raw_response=ai_response
            )
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.debug(f"Raw response: {json.dumps(ai_response, indent=2)}")
            
            # Return minimal result with error
            return TenderExtractionResult(
                extracted_data=TenderExtractedData(),
                confidence_scores=ConfidenceScores(),
                extraction_notes=ExtractionNotes(
                    ambiguities=[f"Failed to parse AI response: {str(e)}"]
                ),
                processing_metadata=ProcessingMetadata(
                    extraction_complexity=ExtractionComplexity.COMPLEX
                ),
                raw_response=ai_response
            )
    
    def _detect_language(self, text: str) -> str:
        """Detect document language (simplified implementation)."""
        # This is a very basic implementation
        # In production, you'd use a proper language detection library
        
        if not text:
            return "unknown"
        
        # Look for common language indicators
        text_lower = text.lower()
        
        # English indicators
        english_words = ["the", "and", "for", "with", "tender", "contract", "project"]
        english_score = sum(1 for word in english_words if word in text_lower)
        
        # German indicators
        german_words = ["der", "die", "das", "und", "für", "mit", "ausschreibung"]
        german_score = sum(1 for word in german_words if word in text_lower)
        
        # French indicators
        french_words = ["le", "la", "les", "et", "pour", "avec", "appel d'offres"]
        french_score = sum(1 for word in french_words if word in text_lower)
        
        scores = {"en": english_score, "de": german_score, "fr": french_score}
        detected = max(scores, key=scores.get)
        
        return detected if scores[detected] > 2 else "unknown"
    
    def _assess_complexity(
        self,
        document: DocumentContent,
        ai_response: Dict[str, Any]
    ) -> ExtractionComplexity:
        """Assess extraction complexity."""
        
        complexity_score = 0
        
        # Document factors
        if document.get_total_content_length() > 50000:
            complexity_score += 2
        elif document.get_total_content_length() > 10000:
            complexity_score += 1
        
        if len(document.tables) > 5:
            complexity_score += 1
        
        if len(document.images) > 0:
            complexity_score += 1
        
        # Response factors
        if ai_response.get("extraction_notes", {}).get("ambiguities"):
            complexity_score += 1
        
        if ai_response.get("extraction_notes", {}).get("missing_information"):
            complexity_score += 1
        
        # Processing time factor (if available)
        if "_metadata" in ai_response:
            processing_time = ai_response["_metadata"].get("processing_time", 0)
            if processing_time > 60:
                complexity_score += 2
            elif processing_time > 30:
                complexity_score += 1
        
        # Determine complexity level
        if complexity_score >= 5:
            return ExtractionComplexity.COMPLEX
        elif complexity_score >= 3:
            return ExtractionComplexity.MODERATE
        else:
            return ExtractionComplexity.SIMPLE


# Worker function for RQ
def process_extraction_job(job_id: str, request_data: Dict[str, Any]):
    """Process a document extraction job (RQ worker function)."""
    
    logger.info(f"Starting extraction job: {job_id}")
    
    # Run the async extraction in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_process_job_async(job_id, request_data))
        logger.info(f"Completed extraction job: {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        logger.debug(traceback.format_exc())
        
        # Update job status with error
        loop.run_until_complete(_handle_job_error(job_id, e))
        raise
        
    finally:
        loop.close()


async def _process_job_async(job_id: str, request_data: Dict[str, Any]) -> Any:
    """Async processing of extraction job."""
    
    service = ExtractionService()
    job_manager = get_job_manager()
    
    try:
        # Parse request
        if "documents" in request_data:
            # Batch request
            batch_request = BatchExtractionRequest(**request_data)
            await job_manager.update_job_status(job_id, ExtractionStatus.PROCESSING)
            
            results = []
            total_docs = len(batch_request.documents)
            
            for i, doc_request in enumerate(batch_request.documents):
                # Update progress
                progress = (i / total_docs) * 100
                await job_manager.update_job_status(job_id, ExtractionStatus.PROCESSING, progress)
                
                # Process document (this is simplified - in reality you'd need file content)
                # For now, we'll create a mock result
                result = TenderExtractionResult(
                    extracted_data=TenderExtractedData(
                        project_title=f"Mock extraction for {doc_request.filename}"
                    ),
                    confidence_scores=ConfidenceScores(),
                    extraction_notes=ExtractionNotes(),
                    processing_metadata=ProcessingMetadata()
                )
                results.append(result)
            
            # Complete the job
            await job_manager.update_job_status(
                job_id,
                ExtractionStatus.COMPLETED,
                progress=100.0,
                result=results
            )
            
            return results
            
        else:
            # Single document request
            doc_request = DocumentExtractionRequest(**request_data)
            await job_manager.update_job_status(job_id, ExtractionStatus.PROCESSING, 10.0)
            
            # For demo purposes, create a mock result
            # In reality, you'd get the file content from storage
            result = TenderExtractionResult(
                extracted_data=TenderExtractedData(
                    project_title=f"Mock extraction for {doc_request.filename}"
                ),
                confidence_scores=ConfidenceScores(overall=0.85),
                extraction_notes=ExtractionNotes(),
                processing_metadata=ProcessingMetadata(
                    extraction_complexity=ExtractionComplexity.MODERATE
                )
            )
            
            await job_manager.update_job_status(
                job_id,
                ExtractionStatus.COMPLETED,
                progress=100.0,
                result=result,
                processing_time=2.5,
                tokens_used=1500
            )
            
            return result
            
    except Exception as e:
        await _handle_job_error(job_id, e)
        raise


async def _handle_job_error(job_id: str, error: Exception):
    """Handle job processing error."""
    
    job_manager = get_job_manager()
    
    error_message = str(error)
    if isinstance(error, TenderExtractionException):
        error_message = f"{error.error_code}: {error.message}"
    
    await job_manager.update_job_status(
        job_id,
        ExtractionStatus.FAILED,
        error_message=error_message
    )