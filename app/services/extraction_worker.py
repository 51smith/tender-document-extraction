import asyncio
import json
import logging
import time
import traceback
from typing import Any, Dict, List, Union

from app.core.exceptions import (
    DocumentProcessingError,
    GeminiAPIException,
    TenderExtractionException,
)
from app.models.extraction import (
    BatchExtractionRequest,
    ConfidenceScores,
    DocumentExtractionRequest,
    ExtractionComplexity,
    ExtractionNotes,
    ExtractionStatus,
    ProcessingMetadata,
    TenderExtractedData,
    TenderExtractionResult,
)
from app.services.gemini_service import get_gemini_client
from app.services.llm_service import get_llm_service
from app.services.job_manager import get_job_manager
from app.utils.document_processor import DocumentContent, get_document_processor
from app.utils.prompt_builder import get_prompt_builder

logger = logging.getLogger(__name__)


class ExtractionService:
    """Core document extraction service."""

    def __init__(self):
        self.llm_service = get_llm_service()  # New configurable LLM service
        self.document_processor = get_document_processor()
        self.prompt_builder = get_prompt_builder()
        self.job_manager = get_job_manager()
        
        # Log the provider configuration for debugging
        logger.info(f"ExtractionService initialized with LLM provider: {self.llm_service.get_provider_name()}")
        logger.info(f"ExtractionService LLM model: {self.llm_service.model}")
        logger.info(f"ExtractionService provider info: {self.llm_service.get_provider_info()}")
        
        # Only initialize Gemini client if provider is Gemini (for multimodal and File API features)
        if self.llm_service.get_provider_name() == "gemini":
            logger.info("Initializing Gemini client for multimodal features")
            self.gemini_client = get_gemini_client()
        else:
            logger.info(f"Gemini client not initialized (using {self.llm_service.get_provider_name()} provider)")
            self.gemini_client = None

    async def _process_document_content(
        self, document_content: bytes, request: DocumentExtractionRequest
    ) -> TenderExtractionResult:
        """Process actual document content (simplified version of the removed extract_from_document method)."""

        start_time = time.time()

        try:
            # Process document
            logger.info(f"Processing document: {request.filename}")
            processed_doc = self.document_processor.process_document(
                document_content, request.filename, request.content_type
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
                variables=request.variables,
            )

            # Prepare content for AI processing
            if request.enable_multimodal and processed_doc.images:
                content = self.document_processor.get_multimodal_content(processed_doc)
            else:
                content = prompt_result["prompt"]

            # Extract using configured LLM provider
            logger.info(f"Extracting data from: {request.filename}")
            if isinstance(content, list):  # Multimodal content - requires Gemini client
                if self.gemini_client is None:
                    logger.warning("Multimodal content requested but Gemini client not available. Converting to text-only.")
                    # Convert multimodal content to text-only for non-Gemini providers
                    content = prompt_result["prompt"]
                    ai_response = await self.llm_service.generate_content(content, json_schema={"type": "object"})
                    # Handle LLM service response format
                    if isinstance(ai_response, dict) and "response" in ai_response:
                        try:
                            import json
                            actual_response = json.loads(ai_response["response"])
                        except (json.JSONDecodeError, TypeError):
                            actual_response = ai_response
                    else:
                        actual_response = ai_response
                    extraction_result = self._parse_ai_response(actual_response, processed_doc)
                else:
                    # Use Gemini client for multimodal content
                    ai_response = await self.gemini_client.generate_content(content)
                    extraction_result = self._parse_ai_response(ai_response, processed_doc)
            else:  # Text-only content - use configurable LLM service
                ai_response = await self.llm_service.generate_content(content, json_schema={"type": "object"})
                
                # Handle LLM service response format
                if isinstance(ai_response, dict) and "response" in ai_response:
                    try:
                        import json
                        actual_response = json.loads(ai_response["response"])
                    except (json.JSONDecodeError, TypeError):
                        actual_response = ai_response
                else:
                    actual_response = ai_response
                
                extraction_result = self._parse_ai_response(actual_response, processed_doc)

            # Add processing metadata
            processing_time = time.time() - start_time
            extraction_result.processing_metadata.processing_time = processing_time
            extraction_result.processing_metadata.total_pages = processed_doc.metadata.get(
                "page_count"
            )

            logger.info(
                f"Successfully extracted data from: {request.filename} in {processing_time:.2f}s"
            )
            return extraction_result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Extraction failed for {request.filename}: {e}")
            logger.debug(traceback.format_exc())

            # Return partial result with error information
            return TenderExtractionResult(
                extracted_data=TenderExtractedData(),
                confidence_scores=ConfidenceScores(),
                extraction_notes=ExtractionNotes(ambiguities=[f"Extraction failed: {str(e)}"]),
                processing_metadata=ProcessingMetadata(
                    processing_time=processing_time,
                    extraction_complexity=ExtractionComplexity.COMPLEX,
                ),
                raw_response={"error": str(e), "type": type(e).__name__},
            )

    async def _process_multiple_documents(
        self, documents: Dict[str, bytes], batch_request: BatchExtractionRequest
    ) -> TenderExtractionResult:
        """Process multiple documents using the configured LLM provider."""

        start_time = time.time()

        try:
            logger.info(f"Processing {len(documents)} documents together with {self.llm_service.get_provider_name()} provider")
            logger.info(f"Gemini client is: {'None' if self.gemini_client is None else 'initialized'}")
            logger.info(f"Provider check: llm_service.get_provider_name() == 'gemini': {self.llm_service.get_provider_name() == 'gemini'}")
            logger.info(f"Gemini client check: self.gemini_client is not None: {self.gemini_client is not None}")
            
            # Check provider and route accordingly
            if (self.llm_service.get_provider_name() == "gemini" and 
                self.gemini_client is not None and 
                hasattr(self.gemini_client, 'process_multiple_documents')):
                logger.info("USING GEMINI PATH: Using Gemini File API for multi-document processing")
                # Use Gemini's File API for multi-document processing
                
                # Build a comprehensive prompt for all documents using multi-document template
                prompt_result = self.prompt_builder.build_prompt(
                    document_content="",  # We'll let Gemini analyze the uploaded files directly
                    config_name=batch_request.documents[0].config_name
                    if batch_request.documents
                    else "default",
                    template_override="multi_document_extraction",  # Use multi-document template
                    variables=batch_request.documents[0].variables if batch_request.documents else None,
                )

                # Create a multi-document analysis prompt
                multi_doc_prompt = f"""
{prompt_result['prompt']}

MULTI-DOCUMENT ANALYSIS INSTRUCTIONS:
You have been provided with {len(documents)} documents that should be analyzed together as they may contain related information for the same tender/project.

Documents provided:
{chr(10).join(f"- {filename}" for filename in documents.keys())}

Please analyze ALL documents together and extract the complete tender information. Information may be spread across multiple documents - combine and consolidate the data appropriately.

If the same information appears in multiple documents, use the most complete or recent version.
If there are contradictions between documents, note them in the extraction_notes.ambiguities field.

Return the consolidated extraction results in the specified JSON format.
"""

                # Use the new multi-document processing method
                ai_response = await self.gemini_client.process_multiple_documents(
                    documents=documents, prompt=multi_doc_prompt
                )
            else:
                # For other providers (Ollama, OpenAI), process documents by concatenating text
                logger.info(f"USING NON-GEMINI PATH: Processing documents individually with {self.llm_service.get_provider_name()} provider")
                logger.info(f"Using text concatenation approach for non-Gemini provider")
                
                # Process all documents and extract text
                all_document_texts = []
                document_summaries = []
                
                for filename, content in documents.items():
                    try:
                        processed_doc = self.document_processor.process_document(
                            content, filename, content_type=None
                        )
                        all_document_texts.append(f"=== DOCUMENT: {filename} ===\n{processed_doc.text}\n")
                        document_summaries.append(f"- {filename} ({len(processed_doc.text)} characters)")
                    except Exception as e:
                        logger.warning(f"Failed to process {filename}: {e}")
                        document_summaries.append(f"- {filename} (processing failed: {str(e)})")

                # Build a comprehensive prompt for all documents
                prompt_result = self.prompt_builder.build_prompt(
                    document_content="",  # We'll include document content in the prompt
                    config_name=batch_request.documents[0].config_name
                    if batch_request.documents
                    else "default",
                    template_override="multi_document_extraction",  # Use multi-document template
                    variables=batch_request.documents[0].variables if batch_request.documents else None,
                )

                # Create combined document content
                combined_content = "\n".join(all_document_texts)
                
                # Create a multi-document analysis prompt
                multi_doc_prompt = f"""
{prompt_result['prompt']}

MULTI-DOCUMENT ANALYSIS INSTRUCTIONS:
You have been provided with {len(documents)} documents that should be analyzed together as they may contain related information for the same tender/project.

Documents provided:
{chr(10).join(document_summaries)}

Please analyze ALL documents together and extract the complete tender information. Information may be spread across multiple documents - combine and consolidate the data appropriately.

If the same information appears in multiple documents, use the most complete or recent version.
If there are contradictions between documents, note them in the extraction_notes.ambiguities field.

DOCUMENT CONTENTS:
{combined_content}

Return the consolidated extraction results in the specified JSON format.
"""

                # Use the configurable LLM service
                logger.info(f"Making LLM API call using {self.llm_service.get_provider_name()} provider")
                try:
                    ai_response = await self.llm_service.generate_content(
                        prompt=multi_doc_prompt,
                        json_schema={"type": "object"}  # Request JSON response
                    )
                    logger.info(f"LLM API call successful, response type: {type(ai_response)}")
                except Exception as e:
                    logger.error(f"LLM API call failed: {e} (type: {type(e)})")
                    raise

            # Create a combined document object for parsing (use first document as template)
            first_filename = list(documents.keys())[0]
            first_content = documents[first_filename]

            # Try to process the first document for metadata, but don't fail if it doesn't work
            processed_doc = None
            try:
                # Auto-detect content type instead of assuming PDF
                processed_doc = self.document_processor.process_document(
                    first_content, first_filename, content_type=None
                )
            except Exception as doc_error:
                logger.warning(
                    f"Could not process document {first_filename} for metadata: {doc_error}"
                )
                # Create a minimal document object for parsing
                from app.utils.document_processor import DocumentContent

                processed_doc = DocumentContent(
                    text=f"[Multi-document content - see AI analysis results]",
                    images=[],
                    tables=[],
                    metadata={"filename": first_filename},
                    content_hash=f"multi_doc_{hash(first_filename)}",
                    file_type="unknown",
                    file_size=len(first_content),
                )

            # Parse the AI response - handle different response formats from different providers
            if (self.llm_service.get_provider_name() == "gemini" and 
                self.gemini_client is not None and 
                hasattr(self.gemini_client, 'process_multiple_documents')):
                # Gemini client response format
                extraction_result = self._parse_ai_response(ai_response, processed_doc)
            else:
                # LLM service response format - extract the actual content
                if isinstance(ai_response, dict) and "response" in ai_response:
                    # The response is wrapped in a dict with "response" key for text-based providers
                    try:
                        import json
                        actual_response = json.loads(ai_response["response"])
                    except (json.JSONDecodeError, TypeError):
                        # If not valid JSON, treat as the raw AI response
                        actual_response = ai_response
                else:
                    # Direct JSON response
                    actual_response = ai_response
                
                extraction_result = self._parse_ai_response(actual_response, processed_doc)

            # Add multi-document processing metadata
            processing_time = time.time() - start_time
            extraction_result.processing_metadata.processing_time = processing_time
            extraction_result.processing_metadata.total_pages = sum(
                len(content) // 2000 for content in documents.values()  # Rough estimate
            )

            # Add information about multi-document processing
            if not extraction_result.extraction_notes.processing_notes:
                extraction_result.extraction_notes.processing_notes = []

            extraction_result.extraction_notes.processing_notes.append(
                f"Processed {len(documents)} documents together in single API call"
            )
            extraction_result.extraction_notes.processing_notes.append(
                f"Documents: {', '.join(documents.keys())}"
            )

            logger.info(
                f"Successfully extracted data from {len(documents)} documents in {processing_time:.2f}s"
            )
            return extraction_result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Multi-document extraction failed: {e}")
            logger.debug(traceback.format_exc())

            # Return partial result with error information
            return TenderExtractionResult(
                extracted_data=TenderExtractedData(),
                confidence_scores=ConfidenceScores(),
                extraction_notes=ExtractionNotes(
                    ambiguities=[f"Multi-document extraction failed: {str(e)}"],
                    processing_notes=[f"Attempted to process {len(documents)} documents together"],
                ),
                processing_metadata=ProcessingMetadata(
                    processing_time=processing_time,
                    extraction_complexity=ExtractionComplexity.COMPLEX,
                ),
                raw_response={"error": str(e), "type": type(e).__name__},
            )

    def _parse_ai_response(
        self, ai_response: Dict[str, Any], document: DocumentContent
    ) -> TenderExtractionResult:
        """Parse AI response into structured result."""

        try:
            # Handle different response formats
            if "extracted_data" in ai_response:
                # Response already in expected format
                extracted_data = TenderExtractedData(**ai_response["extracted_data"])
                confidence_scores = ConfidenceScores(**(ai_response.get("confidence_scores", {})))
                extraction_notes = ExtractionNotes(**(ai_response.get("extraction_notes", {})))
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
                raw_response=ai_response,
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
                raw_response=ai_response,
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
        self, document: DocumentContent, ai_response: Dict[str, Any]
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
    
    import os
    from app.config import settings
    
    logger.info(f"Starting extraction job: {job_id}")
    logger.info(f"RQ WORKER ENV - LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'not set')}")
    logger.info(f"RQ WORKER ENV - LLM_MODEL: {os.getenv('LLM_MODEL', 'not set')}")
    logger.info(f"RQ WORKER ENV - GOOGLE_API_KEY set: {bool(os.getenv('GOOGLE_API_KEY'))}")
    logger.info(f"RQ WORKER SETTINGS - llm_provider: {settings.llm_provider}")
    logger.info(f"RQ WORKER SETTINGS - llm_model: {settings.llm_model}")
    logger.info(f"RQ WORKER SETTINGS - google_api_key set: {bool(settings.google_api_key)}")

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

        # Update job status with error - use try/except to handle closed loop
        try:
            loop.run_until_complete(_handle_job_error(job_id, e, None))
        except RuntimeError as loop_error:
            if "Event loop is closed" in str(loop_error):
                # Create new loop for error handling
                error_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(error_loop)
                try:
                    error_loop.run_until_complete(_handle_job_error(job_id, e, None))
                finally:
                    error_loop.close()
            else:
                raise
        raise

    finally:
        # Ensure loop is properly closed
        if loop.is_running():
            loop.stop()
        if not loop.is_closed():
            loop.close()


async def _process_job_async(job_id: str, request_data: Dict[str, Any]) -> Any:
    """Async processing of extraction job."""
    
    logger.info(f"Creating ExtractionService instance for job: {job_id}")
    service = ExtractionService()
    logger.info(f"RQ JOB SERVICE - Provider: {service.llm_service.get_provider_name()}")
    logger.info(f"RQ JOB SERVICE - Model: {service.llm_service.model}")
    logger.info(f"RQ JOB SERVICE - Gemini client: {'None' if service.gemini_client is None else 'initialized'}")

    # Create a fresh job manager instance for this event loop
    from app.services.job_manager import JobManager

    job_manager = JobManager()
    await job_manager.initialize()

    try:
        # Get file contents for this job
        file_contents = await job_manager.get_file_contents(job_id)

        # Parse request
        if "documents" in request_data:
            # Batch request - process all documents together in single API call
            batch_request = BatchExtractionRequest(**request_data)
            await job_manager.update_job_status(job_id, ExtractionStatus.PROCESSING, 10.0)

            # Filter out any documents that don't have file content
            available_documents = {
                filename: content
                for filename, content in file_contents.items()
                if content is not None
            }

            missing_files = set(doc.filename for doc in batch_request.documents) - set(
                available_documents.keys()
            )
            if missing_files:
                logger.warning(f"Missing file contents for: {missing_files}")

            if available_documents:
                # Process all documents together in single Gemini API call
                await job_manager.update_job_status(job_id, ExtractionStatus.PROCESSING, 50.0)

                result = await service._process_multiple_documents(
                    available_documents, batch_request
                )

                # Complete the job with single consolidated result
                await job_manager.update_job_status(
                    job_id, ExtractionStatus.COMPLETED, progress=100.0, result=[result]
                )

                return [result]
            else:
                # No documents available - create error result
                error_result = TenderExtractionResult(
                    extracted_data=TenderExtractedData(
                        project_title="No document content available for processing"
                    ),
                    confidence_scores=ConfidenceScores(),
                    extraction_notes=ExtractionNotes(
                        ambiguities=["No file content found for any documents in batch"],
                        processing_notes=[
                            f"Expected documents: {[doc.filename for doc in batch_request.documents]}"
                        ],
                    ),
                    processing_metadata=ProcessingMetadata(),
                )

                await job_manager.update_job_status(
                    job_id, ExtractionStatus.COMPLETED, progress=100.0, result=[error_result]
                )

                return [error_result]

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
                ),
            )

            await job_manager.update_job_status(
                job_id,
                ExtractionStatus.COMPLETED,
                progress=100.0,
                result=result,
                processing_time=2.5,
                tokens_used=1500,
            )

            return result

    except Exception as e:
        await _handle_job_error(job_id, e, job_manager)
        raise
    finally:
        # Clean up job manager connections
        if job_manager._redis_client:
            await job_manager._redis_client.close()


async def _handle_job_error(job_id: str, error: Exception, job_manager=None):
    """Handle job processing error."""

    if job_manager is None:
        # Create a fresh job manager instance for this event loop
        from app.services.job_manager import JobManager

        job_manager = JobManager()
        await job_manager.initialize()
        should_close = True
    else:
        should_close = False

    try:
        error_message = str(error)
        if isinstance(error, TenderExtractionException):
            error_message = f"{error.error_code}: {error.message}"

        await job_manager.update_job_status(
            job_id, ExtractionStatus.FAILED, error_message=error_message
        )
    finally:
        if should_close and job_manager._redis_client:
            await job_manager._redis_client.close()
