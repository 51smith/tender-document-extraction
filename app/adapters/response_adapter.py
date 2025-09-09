"""
Response adapter interface and implementations for different LLM providers.

This module provides a standard interface for transforming provider-specific
response formats into the unified TenderExtractedData format.
"""

import json
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from app.models.extraction import ContractType, TenderExtractedData, ValueType

logger = logging.getLogger(__name__)


class ResponseAdapter(ABC):
    """Abstract base class for response adapters."""

    @abstractmethod
    def adapt_response(self, raw_response: dict[str, Any]) -> TenderExtractedData:
        """
        Transform provider-specific response into unified format.

        Args:
            raw_response: Raw response from LLM provider

        Returns:
            TenderExtractedData: Standardized extraction result

        Raises:
            ValueError: If response format is invalid or cannot be adapted
        """

    def _safe_decimal_conversion(self, value: Any) -> Decimal | None:
        """Safely convert value to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, Exception):
            logger.warning(f"Could not convert {value} to Decimal")
            return None

    def _safe_enum_conversion(self, value: Any, enum_class) -> Any | None:
        """Safely convert value to enum."""
        if value is None:
            return None
        try:
            if isinstance(value, str):
                # Try direct value match first
                for enum_value in enum_class:
                    if enum_value.value.lower() == value.lower():
                        return enum_value
                # If no match, return first enum value as default
                return next(iter(enum_class))
        except (ValueError, AttributeError):
            logger.warning(f"Could not convert {value} to {enum_class.__name__}")
        return None

    def _transform_npo_format(self, raw_response: dict[str, Any]) -> TenderExtractedData:
        """
        Transform NPO alternative format (tender_documents/procurement_process)
        to TenderExtractedData.
        This method is shared between GeminiResponseAdapter and OllamaResponseAdapter.
        """
        logger.info("=== STARTING NPO FORMAT TRANSFORMATION ===")
        try:
            adapted_data = {}
            logger.debug("Initialized empty adapted_data dictionary")

            # Handle project_title - extract from tender_documents
            logger.info("=== PROCESSING PROJECT_TITLE (NPO format) ===")
            if "project_title" in raw_response:
                logger.info(f"Found direct project_title: {raw_response['project_title']}")
                adapted_data["project_title"] = raw_response["project_title"]
            elif "tender_documents" in raw_response and raw_response["tender_documents"]:
                logger.info("Looking for project_title in tender_documents")
                docs = raw_response["tender_documents"]
                logger.debug(f"tender_documents type: {type(docs)}, content: {docs}")
                if isinstance(docs, list) and docs:
                    title = None
                    for i, doc in enumerate(docs):
                        logger.debug(f"Processing document {i}: {type(doc)}")
                        if isinstance(doc, dict):
                            doc_title = doc.get("title", "")
                            logger.debug(f"Doc {i} title: '{doc_title}'")
                            if doc_title and doc_title not in ["", "Unknown", "N/A"]:
                                title = doc_title
                                logger.info(f"Found meaningful title in document {i}: '{title}'")
                                break

                    if not title and docs:
                        first_doc = docs[0]
                        if isinstance(first_doc, dict):
                            title = first_doc.get("title", "NPO Tender Document")
                            logger.info(f"Using fallback title from first doc: '{title}'")

                    if title:
                        adapted_data["project_title"] = title
                        logger.info(f"Final extracted project_title: '{title}'")
                    else:
                        adapted_data["project_title"] = "NPO Tender Document"
                        logger.info("Using last resort fallback title: 'NPO Tender Document'")
                else:
                    logger.warning(f"tender_documents is not a valid list: {type(docs)}")
                    adapted_data["project_title"] = "NPO Tender Document"
            else:
                logger.info("No project_title found in response")
                adapted_data["project_title"] = None

            # Handle estimated_value - transform from simple format or extract from data
            logger.info("=== PROCESSING ESTIMATED_VALUE (NPO format) ===")
            estimated_value = self._adapt_estimated_value(raw_response)
            if estimated_value:
                adapted_data["estimated_value"] = estimated_value
                logger.info(f"Adapted estimated_value: {estimated_value}")
            else:
                logger.info("No estimated_value found or adapted")

            # Handle contracting_authority - detect NPO format
            logger.info("=== PROCESSING CONTRACTING_AUTHORITY (NPO format) ===")
            contracting_authority = self._adapt_contracting_authority(raw_response)
            if contracting_authority:
                adapted_data["contracting_authority"] = contracting_authority
                logger.info(f"Adapted contracting_authority: {contracting_authority}")
            else:
                logger.info("No contracting_authority found or adapted")

            # Handle evaluation_criteria - transform field names and weights
            logger.info("=== PROCESSING EVALUATION_CRITERIA (NPO format) ===")
            evaluation_criteria = self._adapt_evaluation_criteria(raw_response)
            if evaluation_criteria:
                adapted_data["evaluation_criteria"] = evaluation_criteria
                logger.info(f"Adapted evaluation_criteria count: {len(evaluation_criteria)}")
            else:
                # Try to extract evaluation_criteria from tender_documents
                logger.info("No top-level evaluation_criteria, checking tender_documents")
                if "tender_documents" in raw_response:
                    docs = raw_response["tender_documents"]
                    if isinstance(docs, list):
                        for doc in docs:
                            if isinstance(doc, dict) and "evaluation_criteria" in doc:
                                logger.info("Found evaluation_criteria in tender_documents")
                                doc_criteria = self._adapt_evaluation_criteria(
                                    {"evaluation_criteria": doc["evaluation_criteria"]}
                                )
                                if doc_criteria:
                                    adapted_data["evaluation_criteria"] = doc_criteria
                                    logger.info(
                                        f"Adapted evaluation_criteria count: {len(doc_criteria)}"
                                    )
                                    break

                if "evaluation_criteria" not in adapted_data:
                    logger.info("No evaluation_criteria found or adapted")

            # Handle functional_requirements - extract from tender_documents or procurement_process
            logger.info("=== PROCESSING FUNCTIONAL_REQUIREMENTS (NPO format) ===")
            if "functional_requirements" not in raw_response:
                logger.info("No direct functional_requirements, extracting from documents")
                functional_reqs = []

                # Check tender_documents for requirements
                if "tender_documents" in raw_response:
                    logger.info("Processing tender_documents for functional requirements")
                    docs = raw_response["tender_documents"]
                    if isinstance(docs, list):
                        logger.debug(f"Found {len(docs)} tender documents")
                        for i, doc in enumerate(docs):
                            if isinstance(doc, dict):
                                title = doc.get("title", "")
                                desc = doc.get("description", "")
                                logger.debug(f"Document {i}: title='{title}', desc='{desc}'")
                                if title and desc:
                                    req_text = f"{title}: {desc}"
                                    functional_reqs.append(req_text)
                                    logger.debug(f"Added functional requirement: '{req_text}'")

                # Check procurement_process for additional requirements
                if "procurement_process" in raw_response:
                    logger.info("Processing procurement_process for functional requirements")
                    process = raw_response["procurement_process"]
                    if isinstance(process, list):
                        logger.debug(f"Found {len(process)} procurement steps")
                        for i, step in enumerate(process):
                            if isinstance(step, dict):
                                title = step.get("title", step.get("phase", ""))
                                desc = step.get("description", "")
                                logger.debug(f"Step {i}: title='{title}', desc='{desc}'")
                                if title and desc:
                                    req_text = f"Process: {title} - {desc}"
                                    functional_reqs.append(req_text)
                                    logger.debug(f"Added process requirement: '{req_text}'")

                if functional_reqs:
                    adapted_data["functional_requirements"] = functional_reqs
                    logger.info(f"Extracted {len(functional_reqs)} functional requirements")
                else:
                    logger.info("No functional requirements extracted")
            else:
                logger.info("Using direct functional_requirements from response")
                adapted_data["functional_requirements"] = raw_response["functional_requirements"]

            # Handle submission_requirements - NPO complaint_procedure mapping
            logger.info("=== PROCESSING SUBMISSION_REQUIREMENTS (NPO format) ===")
            if "submission_requirements" in raw_response:
                adapted_data["submission_requirements"] = raw_response["submission_requirements"]
                logger.info("Using direct submission_requirements from response")
            elif "complaint_procedure" in raw_response:
                from app.models.extraction import SubmissionRequirements

                complaint = raw_response["complaint_procedure"]
                logger.debug(f"Processing complaint_procedure: {complaint}")

                if isinstance(complaint, dict):
                    description = complaint.get("description", "")
                    deadline = complaint.get("deadline", "")
                    method = complaint.get("method", "")

                    req_docs = []
                    if description:
                        req_docs.append(f"Complaint: {description}")

                    submission_method = []
                    if method:
                        submission_method.append(f"Method: {method}")
                    if deadline:
                        submission_method.append(f"Deadline: {deadline}")

                    adapted_data["submission_requirements"] = SubmissionRequirements(
                        documents_required=req_docs if req_docs else None,
                        submission_method=" | ".join(submission_method)
                        if submission_method
                        else None,
                    )
                    logger.info("Mapped complaint_procedure to submission_requirements")
                elif isinstance(complaint, str):
                    adapted_data["submission_requirements"] = SubmissionRequirements(
                        documents_required=[f"Complaint procedure: {complaint}"],
                        submission_method=None,
                    )
                    logger.info(
                        "Mapped simple complaint_procedure string to submission_requirements"
                    )
            else:
                logger.info("No submission_requirements related fields found")

            # Handle direct mappings
            direct_fields = [
                "submission_deadline",
                "project_duration",
                "contract_start_date",
                "contract_type",
                "cpv_codes",
                "procurement_procedure",
                "technical_requirements",
                "eligibility_criteria",
                "knockout_criteria",
                "special_conditions",
                "reference_number",
                "publication_date",
            ]

            for field in direct_fields:
                if field in raw_response:
                    value = raw_response[field]
                    if field == "contract_type":
                        from app.models.extraction import ContractType

                        value = self._safe_enum_conversion(value, ContractType)
                    adapted_data[field] = value

            # Add NPO-specific fields to capture more data from raw response
            logger.info("=== PROCESSING NPO-SPECIFIC FIELDS ===")

            # Handle procurement_phases - extract from procurement_process
            if "procurement_process" in raw_response:
                from app.models.extraction import ProcurementPhase

                phases = []
                process = raw_response["procurement_process"]
                if isinstance(process, list):
                    logger.debug(f"Found {len(process)} procurement process steps")
                    for i, step in enumerate(process):
                        if isinstance(step, dict):
                            phase_obj = ProcurementPhase(
                                phase=step.get("phase", f"Phase {i+1}"),
                                title=step.get("title", step.get("phase")),
                                description=step.get("description"),
                                deadline=step.get("deadline"),
                                status=step.get("status"),
                            )
                            phases.append(phase_obj)
                            logger.debug(f"Added procurement phase: {phase_obj.phase}")

                if phases:
                    adapted_data["procurement_phases"] = phases
                    logger.info(f"Added {len(phases)} procurement phases")

            # Handle complaint_procedure - direct mapping from NPO format
            if "complaint_procedure" in raw_response:
                from app.models.extraction import ComplaintProcedure

                complaint = raw_response["complaint_procedure"]
                if isinstance(complaint, dict):
                    complaint_obj = ComplaintProcedure(
                        description=complaint.get("description"),
                        deadline=complaint.get("deadline"),
                        method=complaint.get("method"),
                        contact_info=complaint.get("contact_info"),
                        authority=complaint.get("authority"),
                    )
                    adapted_data["complaint_procedure"] = complaint_obj
                    logger.info("Added complaint procedure from NPO format")

            # Handle document_structure - extract from tender_documents
            if "tender_documents" in raw_response:
                from app.models.extraction import DocumentStructure

                docs = []
                tender_docs = raw_response["tender_documents"]
                if isinstance(tender_docs, list):
                    logger.debug(f"Found {len(tender_docs)} tender documents")
                    for i, doc in enumerate(tender_docs):
                        if isinstance(doc, dict):
                            # Handle page_references - could be 'pages' or 'page_references'
                            page_refs = doc.get("page_references", doc.get("pages", []))
                            if isinstance(page_refs, str):
                                page_refs = [page_refs]
                            elif not isinstance(page_refs, list):
                                page_refs = []

                            doc_obj = DocumentStructure(
                                title=doc.get("title", f"Document {i+1}"),
                                description=doc.get("description"),
                                document_type=doc.get("document_type", "tender_document"),
                                section=doc.get("section"),
                                page_references=page_refs,
                            )
                            docs.append(doc_obj)
                            logger.debug(f"Added document structure: {doc_obj.title}")

                if docs:
                    adapted_data["document_structure"] = docs
                    logger.info(f"Added {len(docs)} document structures")

            # Handle exclusion_grounds and selection_criteria - extract from related fields
            if "exclusion_grounds" in raw_response:
                exclusion = raw_response["exclusion_grounds"]
                if isinstance(exclusion, list):
                    adapted_data["exclusion_grounds"] = exclusion
                    logger.info(f"Added {len(exclusion)} exclusion grounds")
                elif isinstance(exclusion, str):
                    adapted_data["exclusion_grounds"] = [exclusion]
                    logger.info("Added single exclusion ground")

            if "selection_criteria" in raw_response:
                selection = raw_response["selection_criteria"]
                if isinstance(selection, list):
                    adapted_data["selection_criteria"] = selection
                    logger.info(f"Added {len(selection)} selection criteria")
                elif isinstance(selection, str):
                    adapted_data["selection_criteria"] = [selection]
                    logger.info("Added single selection criterion")

            if "application_conditions" in raw_response:
                conditions = raw_response["application_conditions"]
                if isinstance(conditions, list):
                    adapted_data["application_conditions"] = conditions
                    logger.info(f"Added {len(conditions)} application conditions")
                elif isinstance(conditions, str):
                    adapted_data["application_conditions"] = [conditions]
                    logger.info("Added single application condition")

            logger.info("=== FINALIZING NPO TRANSFORMATION ===")
            logger.info(f"Adapted data keys: {list(adapted_data.keys())}")
            logger.debug(
                f"Final adapted_data content: {json.dumps(adapted_data, indent=2, default=str)}"
            )

            # Create and validate the result
            result = TenderExtractedData(**adapted_data)
            logger.info("Successfully created TenderExtractedData object")
            logger.info(f"Result project_title: {result.project_title}")
            logger.info(
                f"Result functional_requirements count: "
                f"{len(result.functional_requirements) if result.functional_requirements else 0}"
            )
            logger.info(
                f"Result evaluation_criteria count: "
                f"{len(result.evaluation_criteria) if result.evaluation_criteria else 0}"
            )
            logger.info("=== NPO TRANSFORMATION COMPLETED SUCCESSFULLY ===")
            return result

        except Exception as npo_error:
            logger.exception("=== NPO TRANSFORMATION FAILED ===")
            logger.info(f"Available response keys: {list(raw_response.keys())}")
            raise ValueError(
                f"Invalid NPO response format. Transformation failed: {npo_error}"
            ) from npo_error


class GeminiResponseAdapter(ResponseAdapter):
    """Response adapter for Google Gemini responses."""

    def adapt_response(self, raw_response: dict[str, Any]) -> TenderExtractedData:
        """
        Adapt Gemini response format to TenderExtractedData.

        Gemini typically returns well-structured responses that closely
        match our target format, but we also handle alternative formats
        like tender_documents/procurement_process structure.
        """
        logger.info("=== GeminiResponseAdapter STARTING TRANSFORMATION ===")
        logger.info(f"Raw response keys: {list(raw_response.keys())}")
        try:
            logger.debug(f"Full raw response: {json.dumps(raw_response, indent=2, default=str)}")
        except (TypeError, ValueError):
            logger.debug(f"Full raw response (non-JSON): {raw_response}")

        # Check if response uses alternative format (tender_documents/procurement_process structure)
        response_fields = set(raw_response.keys())
        has_alternative_format = {"tender_documents", "procurement_process"}.intersection(
            response_fields
        )

        logger.info(f"Alternative format detection: {has_alternative_format}")
        logger.info(f"Detected fields: {response_fields}")

        # Try direct construction first, unless we detect the alternative format
        if not has_alternative_format:
            logger.info("No alternative format detected, trying direct construction")
            try:
                result = TenderExtractedData(**raw_response)
                logger.info("Direct construction succeeded")
                return result
            except Exception as e:
                logger.warning(f"Direct Gemini response construction failed: {e}")
                logger.info("Falling back to NPO transformation logic")
                return self._transform_npo_format(raw_response)
        else:
            logger.info("Response uses alternative format, applying NPO transformation logic")
            # Use the NPO transformation logic for alternative formats
            return self._transform_npo_format(raw_response)
        try:
            adapted_data = {}
            logger.debug("Initialized empty adapted_data dictionary")

            # Handle project_title - check multiple possible sources
            logger.info("=== PROCESSING PROJECT_TITLE ===")
            if "project_title" in raw_response:
                logger.info(f"Found direct project_title: {raw_response['project_title']}")
                adapted_data["project_title"] = raw_response["project_title"]
            elif "tender_documents" in raw_response and raw_response["tender_documents"]:
                logger.info("Looking for project_title in tender_documents")
                # Try to extract title from tender_documents
                docs = raw_response["tender_documents"]
                logger.debug(f"tender_documents type: {type(docs)}, content: {docs}")
                if isinstance(docs, list) and docs:
                    # Look for the first meaningful title in documents
                    title = None
                    for i, doc in enumerate(docs):
                        logger.debug(f"Processing document {i}: {type(doc)}")
                        if isinstance(doc, dict):
                            doc_title = doc.get("title", "")
                            doc_desc = doc.get("description", "")
                            logger.debug(f"Doc {i} title: '{doc_title}', description: '{doc_desc}'")

                            # Skip empty or generic titles, look for meaningful ones
                            if doc_title and doc_title not in ["", "Unknown", "N/A"]:
                                title = doc_title
                                logger.info(f"Found meaningful title in document {i}: '{title}'")
                                break

                    if not title and docs:
                        # Fallback to first document with any title
                        first_doc = docs[0]
                        if isinstance(first_doc, dict):
                            title = first_doc.get("title", "NPO Tender Document")
                            logger.info(f"Using fallback title from first doc: '{title}'")

                    if title:
                        adapted_data["project_title"] = title
                        logger.info(f"Final extracted project_title: '{title}'")
                    else:
                        # Last resort fallback
                        adapted_data["project_title"] = "NPO Tender Document"
                        logger.info("Using last resort fallback title: 'NPO Tender Document'")
                else:
                    logger.warning(f"tender_documents is not a valid list: {type(docs)}")
                    adapted_data["project_title"] = "NPO Tender Document"
            else:
                logger.info("No project_title found in response")
                # Leave as None for invalid responses
                adapted_data["project_title"] = None

            # Handle estimated_value - transform from simple format or extract from data
            logger.info("=== PROCESSING ESTIMATED_VALUE ===")
            estimated_value = self._adapt_estimated_value(raw_response)
            if estimated_value:
                adapted_data["estimated_value"] = estimated_value
                logger.info(f"Adapted estimated_value: {estimated_value}")
            else:
                logger.info("No estimated_value found or adapted")

            # Handle contracting_authority - build nested structure
            logger.info("=== PROCESSING CONTRACTING_AUTHORITY ===")
            contracting_authority = self._adapt_contracting_authority(raw_response)
            if contracting_authority:
                adapted_data["contracting_authority"] = contracting_authority
                logger.info(f"Adapted contracting_authority: {contracting_authority}")
            else:
                logger.info("No contracting_authority found or adapted")

            # Handle evaluation_criteria - transform field names and weights
            logger.info("=== PROCESSING EVALUATION_CRITERIA ===")
            evaluation_criteria = self._adapt_evaluation_criteria(raw_response)
            if evaluation_criteria:
                adapted_data["evaluation_criteria"] = evaluation_criteria
                logger.info(f"Adapted evaluation_criteria count: {len(evaluation_criteria)}")
                for i, criterion in enumerate(evaluation_criteria):
                    logger.debug(f"Criterion {i}: {criterion}")
            else:
                logger.info("No evaluation_criteria found or adapted")

            # Handle functional_requirements - extract from tender_documents or procurement_process
            logger.info("=== PROCESSING FUNCTIONAL_REQUIREMENTS ===")
            if "functional_requirements" not in raw_response:
                logger.info("No direct functional_requirements, extracting from documents")
                functional_reqs = []

                # Check tender_documents for requirements
                if "tender_documents" in raw_response:
                    logger.info("Processing tender_documents for functional requirements")
                    docs = raw_response["tender_documents"]
                    if isinstance(docs, list):
                        logger.debug(f"Found {len(docs)} tender documents")
                        for i, doc in enumerate(docs):
                            if isinstance(doc, dict):
                                title = doc.get("title", "")
                                desc = doc.get("description", "")
                                logger.debug(f"Document {i}: title='{title}', desc='{desc}'")
                                if title and desc:
                                    req_text = f"{title}: {desc}"
                                    functional_reqs.append(req_text)
                                    logger.debug(f"Added functional requirement: '{req_text}'")

                # Check procurement_process for additional requirements
                if "procurement_process" in raw_response:
                    logger.info("Processing procurement_process for functional requirements")
                    process = raw_response["procurement_process"]
                    if isinstance(process, list):
                        logger.debug(f"Found {len(process)} procurement steps")
                        for i, step in enumerate(process):
                            if isinstance(step, dict):
                                title = step.get("title", step.get("phase", ""))
                                desc = step.get("description", "")
                                logger.debug(f"Step {i}: title='{title}', desc='{desc}'")
                                if title and desc:
                                    req_text = f"Process: {title} - {desc}"
                                    functional_reqs.append(req_text)
                                    logger.debug(f"Added process requirement: '{req_text}'")

                if functional_reqs:
                    adapted_data["functional_requirements"] = functional_reqs
                    logger.info(f"Extracted {len(functional_reqs)} functional requirements")
                else:
                    logger.info("No functional requirements extracted")
            else:
                logger.info("Using direct functional_requirements from response")
                adapted_data["functional_requirements"] = raw_response["functional_requirements"]

            # Handle technical_requirements - look for technical specs
            if "technical_requirements" not in raw_response:
                tech_reqs = []

                # Look for technical information in various fields
                for field_name in [
                    "technische_eisen",
                    "technical_specifications",
                    "specifications",
                ]:
                    if field_name in raw_response:
                        tech_data = raw_response[field_name]
                        if isinstance(tech_data, list):
                            tech_reqs.extend([str(item) for item in tech_data])
                        elif tech_data:
                            tech_reqs.append(str(tech_data))

                if tech_reqs:
                    adapted_data["technical_requirements"] = tech_reqs

            # Handle direct mappings
            direct_fields = [
                "submission_deadline",
                "project_duration",
                "contract_start_date",
                "contract_type",
                "cpv_codes",
                "procurement_procedure",
                "functional_requirements",
                "technical_requirements",
                "eligibility_criteria",
                "knockout_criteria",
                "special_conditions",
                "reference_number",
                "publication_date",
            ]

            for field in direct_fields:
                if field in raw_response:
                    value = raw_response[field]
                    if field == "contract_type":
                        value = self._safe_enum_conversion(value, ContractType)
                    adapted_data[field] = value

            # Handle lot_structure if present
            if "lot_structure" in raw_response:
                adapted_data["lot_structure"] = raw_response["lot_structure"]

            # Handle submission_requirements if present
            logger.info("=== PROCESSING SUBMISSION_REQUIREMENTS ===")
            if "submission_requirements" in raw_response:
                adapted_data["submission_requirements"] = raw_response["submission_requirements"]
                logger.info("Using direct submission_requirements from response")
            elif "bezwaar_maken" in raw_response:
                # Map Dutch complaint process to submission requirements
                from app.models.extraction import SubmissionRequirements

                bezwaar = raw_response["bezwaar_maken"]
                if isinstance(bezwaar, dict):
                    req_docs = [bezwaar.get("description", "")]
                    deadline_info = bezwaar.get("deadline", "")
                    adapted_data["submission_requirements"] = SubmissionRequirements(
                        documents_required=req_docs,
                        submission_method=f"Bezwaar deadline: {deadline_info}"
                        if deadline_info
                        else None,
                    )
                    logger.info("Mapped bezwaar_maken to submission_requirements")
            elif "complaint_procedure" in raw_response:
                # Map NPO complaint procedure to submission requirements
                from app.models.extraction import SubmissionRequirements

                complaint = raw_response["complaint_procedure"]
                logger.debug(f"Processing complaint_procedure: {complaint}")

                if isinstance(complaint, dict):
                    # Extract relevant information from complaint procedure
                    description = complaint.get("description", "")
                    deadline = complaint.get("deadline", "")
                    method = complaint.get("method", "")

                    req_docs = []
                    if description:
                        req_docs.append(f"Complaint: {description}")

                    submission_method = []
                    if method:
                        submission_method.append(f"Method: {method}")
                    if deadline:
                        submission_method.append(f"Deadline: {deadline}")

                    adapted_data["submission_requirements"] = SubmissionRequirements(
                        documents_required=req_docs if req_docs else None,
                        submission_method=" | ".join(submission_method)
                        if submission_method
                        else None,
                    )
                    logger.info("Mapped complaint_procedure to submission_requirements")
                elif isinstance(complaint, str):
                    adapted_data["submission_requirements"] = SubmissionRequirements(
                        documents_required=[f"Complaint procedure: {complaint}"],
                        submission_method=None,
                    )
                    logger.info(
                        "Mapped simple complaint_procedure string to submission_requirements"
                    )
            else:
                logger.info("No submission_requirements related fields found")

            logger.info("=== FINALIZING TRANSFORMATION ===")
            logger.info(f"Adapted data keys: {list(adapted_data.keys())}")
            logger.debug(
                f"Final adapted_data content: {json.dumps(adapted_data, indent=2, default=str)}"
            )

            # Create and validate the result
            result = TenderExtractedData(**adapted_data)
            logger.info("Successfully created TenderExtractedData object")
            logger.info(f"Result project_title: {result.project_title}")
            logger.info(
                f"Result functional_requirements count: "
                f"{len(result.functional_requirements) if result.functional_requirements else 0}"
            )
            logger.info(
                f"Result evaluation_criteria count: "
                f"{len(result.evaluation_criteria) if result.evaluation_criteria else 0}"
            )
            logger.info("=== TRANSFORMATION COMPLETED SUCCESSFULLY ===")
            return result

        except Exception as fallback_error:
            logger.exception("=== TRANSFORMATION FAILED ===")
            logger.info(f"Available response keys: {list(raw_response.keys())}")
            raise ValueError(
                f"Invalid Gemini response format. Transformation failed: {fallback_error}"
            ) from fallback_error

    def _adapt_estimated_value(self, raw_response: dict[str, Any]) -> dict[str, Any] | None:
        """Transform estimated_value from various formats."""
        if "estimated_value" not in raw_response:
            return None

        value = raw_response["estimated_value"]

        # If already in correct format, return as-is
        if isinstance(value, dict) and "amount" in value:
            return value

        # Handle simple numeric value
        if isinstance(value, int | float | str):
            amount = self._safe_decimal_conversion(value)
            if amount:
                return {
                    "amount": amount,
                    "currency": raw_response.get("currency", "EUR"),
                    "value_type": ValueType.TOTAL.value,
                    "vat_included": raw_response.get("vat_included"),
                }

        return None

    def _adapt_contracting_authority(self, raw_response: dict[str, Any]) -> dict[str, Any] | None:
        """Transform contracting_authority from various formats."""
        logger.debug("_adapt_contracting_authority called")

        # Try direct contracting_authority field first
        if "contracting_authority" in raw_response:
            logger.debug("Found contracting_authority field")
            authority = raw_response["contracting_authority"]

            # If already in correct format, return as-is
            if isinstance(authority, dict) and "name" in authority:
                # Ensure address structure if present
                if "address" in authority and isinstance(authority["address"], dict):
                    address = authority["address"]
                    if not isinstance(address, dict):
                        authority["address"] = {"city": str(address)}
                logger.debug(f"Using existing contracting_authority structure: {authority}")
                return authority

            # Handle simple string format
            if isinstance(authority, str):
                result = {"name": authority}
                logger.debug(f"Converted string contracting_authority to structure: {result}")
                return result

        # Try to extract from procurement_process if available (NPO format)
        if "procurement_process" in raw_response:
            logger.debug("Looking for contracting authority in procurement_process")
            process = raw_response["procurement_process"]
            if isinstance(process, list):
                for i, step in enumerate(process):
                    if isinstance(step, dict):
                        # Look for authority information in process steps
                        title = step.get("title", step.get("phase", ""))
                        description = step.get("description", "")
                        logger.debug(f"Process step {i}: title='{title}', desc='{description}'")

                        # Look for authority-related keywords
                        if any(
                            keyword in title.lower()
                            for keyword in [
                                "authority",
                                "contracting",
                                "opdrachtgever",
                                "aanbestedende",
                            ]
                        ):
                            authority_name = title if title else description
                            if authority_name:
                                result = {"name": authority_name}
                                logger.debug(
                                    f"Extracted contracting_authority from procurement_process: "
                                    f"{result}"
                                )
                                return result

        # Try to extract from tender_documents (look for NPO or similar)
        if "tender_documents" in raw_response:
            logger.debug("Looking for contracting authority in tender_documents")
            docs = raw_response["tender_documents"]
            if isinstance(docs, list):
                for i, doc in enumerate(docs):
                    if isinstance(doc, dict):
                        title = doc.get("title", "")
                        description = doc.get("description", "")
                        logger.debug(f"Document {i}: title='{title}', desc='{description}'")

                        # Look for NPO or authority patterns
                        if any(
                            keyword in title.lower()
                            for keyword in [
                                "npo",
                                "nederlandse publieke omroep",
                                "authority",
                                "opdrachtgever",
                            ]
                        ):
                            # Extract organization name
                            if "npo" in title.lower():
                                result = {"name": "Nederlandse Publieke Omroep (NPO)"}
                                logger.debug(f"Detected NPO as contracting authority: {result}")
                                return result
                            else:
                                result = {"name": title}
                                logger.debug(
                                    f"Extracted contracting_authority from tender_documents: "
                                    f"{result}"
                                )
                                return result

        # Fallback: if this looks like NPO data, use NPO as default
        response_keys = set(raw_response.keys())
        if {"tender_documents", "evaluation_criteria"}.issubset(response_keys):
            # This looks like NPO format (has tender_documents + evaluation_criteria)
            logger.debug(
                "Detected NPO format structure, using NPO as default contracting authority"
            )
            return {"name": "Nederlandse Publieke Omroep (NPO)"}

        logger.debug("No contracting_authority found")
        return None

    def _adapt_evaluation_criteria(
        self, raw_response: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """Transform evaluation_criteria from various formats."""
        logger.debug("_adapt_evaluation_criteria called")
        if "evaluation_criteria" not in raw_response:
            logger.debug("No evaluation_criteria field found")
            return None

        criteria = raw_response["evaluation_criteria"]
        logger.debug(f"Found evaluation_criteria: {criteria}")
        if not isinstance(criteria, list):
            logger.warning(f"evaluation_criteria is not a list: {type(criteria)}")
            return None

        adapted_criteria = []
        for i, criterion in enumerate(criteria):
            logger.debug(f"Processing criterion {i}: {criterion}")
            if isinstance(criterion, dict):
                adapted_criterion = {}

                # Map 'name' field to 'criterion' if needed
                if "name" in criterion:
                    adapted_criterion["criterion"] = criterion["name"]
                    logger.debug(f"Used 'name' for criterion: {criterion['name']}")
                elif "criterion" in criterion:
                    adapted_criterion["criterion"] = criterion["criterion"]
                    logger.debug(f"Used 'criterion' field: {criterion['criterion']}")
                else:
                    logger.warning(f"No valid criterion name found in: {criterion}")
                    continue  # Skip invalid criteria

                # Transform weight/weightage to weight_percentage
                if "weight" in criterion:
                    weight = criterion["weight"]
                    logger.debug(f"Found weight: {weight}")
                    if isinstance(weight, int | float):
                        # Convert from decimal (0.45) to percentage (45.0)
                        weight_percentage = weight * 100 if weight <= 1.0 else weight
                        adapted_criterion["weight_percentage"] = self._safe_decimal_conversion(
                            weight_percentage
                        )
                        logger.debug(
                            f"Converted weight {weight} to weight_percentage {weight_percentage}"
                        )
                elif "weightage" in criterion:
                    # Handle 'weightage' field from NPO format
                    weightage = criterion["weightage"]
                    logger.debug(f"Found weightage: {weightage}")
                    if isinstance(weightage, int | float):
                        adapted_criterion["weight_percentage"] = self._safe_decimal_conversion(
                            weightage
                        )
                        logger.debug(f"Used weightage {weightage} as weight_percentage")
                elif "weight_percentage" in criterion:
                    adapted_criterion["weight_percentage"] = self._safe_decimal_conversion(
                        criterion["weight_percentage"]
                    )
                    logger.debug(
                        f"Used existing weight_percentage: {criterion['weight_percentage']}"
                    )

                # Copy other fields
                if "description" in criterion:
                    adapted_criterion["description"] = criterion["description"]

                if "sub_criteria" in criterion:
                    adapted_criterion["sub_criteria"] = criterion["sub_criteria"]

                adapted_criteria.append(adapted_criterion)
                logger.debug(f"Added adapted criterion: {adapted_criterion}")
            else:
                logger.warning(f"Criterion {i} is not a dict: {type(criterion)}")

        logger.debug(f"Returning {len(adapted_criteria)} adapted criteria")
        return adapted_criteria if adapted_criteria else None


class OllamaResponseAdapter(ResponseAdapter):
    """Response adapter for Ollama responses."""

    def adapt_response(self, raw_response: dict[str, Any]) -> TenderExtractedData:
        """
        Adapt Ollama response format to TenderExtractedData.

        Ollama can return both standard format and NPO alternative format
        (tender_documents/procurement_process structure). Handle both cases.
        """
        logger.info("=== OllamaResponseAdapter STARTING TRANSFORMATION ===")
        logger.info(f"Raw response keys: {list(raw_response.keys())}")
        try:
            logger.debug(f"Full raw response: {json.dumps(raw_response, indent=2, default=str)}")
        except (TypeError, ValueError):
            logger.debug(f"Full raw response (non-JSON): {raw_response}")

        # Check if response uses NPO alternative format
        # (tender_documents/procurement_process structure)
        response_fields = set(raw_response.keys())
        has_alternative_format = {"tender_documents", "procurement_process"}.intersection(
            response_fields
        )

        logger.info(f"Alternative format detection: {has_alternative_format}")
        logger.info(f"Detected fields: {response_fields}")

        # Try direct construction first, unless we detect the alternative format
        if not has_alternative_format:
            logger.info("No alternative format detected, using standard transformation logic")
        else:
            logger.info(
                "Response uses NPO alternative format, applying transformation "
                "logic similar to Gemini"
            )
            # Use the same transformation logic as GeminiResponseAdapter for NPO format
            return self._transform_npo_format(raw_response)

        try:
            adapted_data = {}

            # Handle project_title - direct mapping
            if "project_title" in raw_response:
                adapted_data["project_title"] = raw_response["project_title"]

            # Handle estimated_value - transform from simple format
            estimated_value = self._adapt_estimated_value(raw_response)
            if estimated_value:
                adapted_data["estimated_value"] = estimated_value

            # Handle contracting_authority - build nested structure
            contracting_authority = self._adapt_contracting_authority(raw_response)
            if contracting_authority:
                adapted_data["contracting_authority"] = contracting_authority

            # Handle evaluation_criteria - transform field names and weights
            evaluation_criteria = self._adapt_evaluation_criteria(raw_response)
            if evaluation_criteria:
                adapted_data["evaluation_criteria"] = evaluation_criteria

            # Handle direct mappings
            direct_fields = [
                "submission_deadline",
                "project_duration",
                "contract_start_date",
                "contract_type",
                "cpv_codes",
                "procurement_procedure",
                "functional_requirements",
                "technical_requirements",
                "eligibility_criteria",
                "knockout_criteria",
                "special_conditions",
                "reference_number",
                "publication_date",
            ]

            for field in direct_fields:
                if field in raw_response:
                    value = raw_response[field]
                    if field == "contract_type":
                        value = self._safe_enum_conversion(value, ContractType)
                    adapted_data[field] = value

            # Handle lot_structure if present
            if "lot_structure" in raw_response:
                adapted_data["lot_structure"] = raw_response["lot_structure"]

            # Handle submission_requirements if present
            if "submission_requirements" in raw_response:
                adapted_data["submission_requirements"] = raw_response["submission_requirements"]

            return TenderExtractedData(**adapted_data)

        except Exception as e:
            logger.exception("Failed to adapt Ollama response")
            raise ValueError(f"Invalid Ollama response format: {e}") from e

    def _adapt_estimated_value(self, raw_response: dict[str, Any]) -> dict[str, Any] | None:
        """Transform estimated_value from various Ollama formats."""
        if "estimated_value" not in raw_response:
            return None

        value = raw_response["estimated_value"]

        # If already in correct format, return as-is
        if isinstance(value, dict) and "amount" in value:
            return value

        # Handle simple numeric value
        if isinstance(value, int | float | str):
            amount = self._safe_decimal_conversion(value)
            if amount:
                return {
                    "amount": amount,
                    "currency": raw_response.get("currency", "EUR"),
                    "value_type": ValueType.TOTAL.value,
                    "vat_included": raw_response.get("vat_included"),
                }

        return None

    def _adapt_contracting_authority(self, raw_response: dict[str, Any]) -> dict[str, Any] | None:
        """Transform contracting_authority from various Ollama formats."""
        if "contracting_authority" not in raw_response:
            return None

        authority = raw_response["contracting_authority"]

        # If already in correct format, return as-is
        if isinstance(authority, dict) and "name" in authority:
            # Ensure address structure if present
            if "address" in authority and isinstance(authority["address"], dict):
                address = authority["address"]
                if not isinstance(address, dict):
                    authority["address"] = {"city": str(address)}
            return authority

        # Handle simple string format
        if isinstance(authority, str):
            return {"name": authority}

        return None

    def _adapt_evaluation_criteria(
        self, raw_response: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """Transform evaluation_criteria from Ollama format."""
        if "evaluation_criteria" not in raw_response:
            return None

        criteria = raw_response["evaluation_criteria"]
        if not isinstance(criteria, list):
            return None

        adapted_criteria = []
        for criterion in criteria:
            if isinstance(criterion, dict):
                adapted_criterion = {}

                # Map 'name' field to 'criterion'
                if "name" in criterion:
                    adapted_criterion["criterion"] = criterion["name"]
                elif "criterion" in criterion:
                    adapted_criterion["criterion"] = criterion["criterion"]
                else:
                    continue  # Skip invalid criteria

                # Transform weight to weight_percentage
                if "weight" in criterion:
                    weight = criterion["weight"]
                    if isinstance(weight, int | float):
                        # Convert from decimal (0.45) to percentage (45.0)
                        weight_percentage = weight * 100 if weight <= 1.0 else weight
                        adapted_criterion["weight_percentage"] = self._safe_decimal_conversion(
                            weight_percentage
                        )
                elif "weight_percentage" in criterion:
                    adapted_criterion["weight_percentage"] = self._safe_decimal_conversion(
                        criterion["weight_percentage"]
                    )

                # Copy other fields
                if "description" in criterion:
                    adapted_criterion["description"] = criterion["description"]

                if "sub_criteria" in criterion:
                    adapted_criterion["sub_criteria"] = criterion["sub_criteria"]

                adapted_criteria.append(adapted_criterion)

        return adapted_criteria if adapted_criteria else None


class OpenAIResponseAdapter(ResponseAdapter):
    """Response adapter for OpenAI responses."""

    def adapt_response(self, raw_response: dict[str, Any]) -> TenderExtractedData:
        """
        Adapt OpenAI response format to TenderExtractedData.

        OpenAI responses are typically well-structured and similar to Gemini,
        but may have some variations in field naming or nesting.
        """
        try:
            # OpenAI responses are generally well-structured
            # Apply minor transformations if needed
            return TenderExtractedData(**raw_response)
        except Exception as e:
            logger.exception("Failed to adapt OpenAI response")
            raise ValueError(f"Invalid OpenAI response format: {e}") from e


class ResponseAdapterFactory:
    """Factory for creating response adapters based on provider."""

    _adapters = {
        "gemini": GeminiResponseAdapter,
        "ollama": OllamaResponseAdapter,
        "openai": OpenAIResponseAdapter,
    }

    @classmethod
    def get_adapter(cls, provider: str) -> ResponseAdapter:
        """
        Get response adapter for the specified provider.

        Args:
            provider: LLM provider name (gemini, ollama, openai)

        Returns:
            ResponseAdapter instance for the provider

        Raises:
            ValueError: If provider is not supported
        """
        if provider not in cls._adapters:
            raise ValueError(
                f"Unsupported provider: {provider}. Supported providers: "
                f"{list(cls._adapters.keys())}"
            )

        return cls._adapters[provider]()

    @classmethod
    def register_adapter(cls, provider: str, adapter_class: type) -> None:
        """
        Register a new response adapter for a provider.

        Args:
            provider: Provider name
            adapter_class: ResponseAdapter subclass
        """
        if not issubclass(adapter_class, ResponseAdapter):
            raise ValueError("adapter_class must be a subclass of ResponseAdapter")

        cls._adapters[provider] = adapter_class
        logger.info(f"Registered response adapter for provider: {provider}")
