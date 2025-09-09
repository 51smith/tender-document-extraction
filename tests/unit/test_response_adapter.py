"""
Tests for response adapters.

This module tests the ResponseAdapter implementations that transform
provider-specific response formats into the unified TenderExtractedData format.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.adapters.response_adapter import (
    GeminiResponseAdapter,
    OllamaResponseAdapter,
    OpenAIResponseAdapter,
    ResponseAdapterFactory,
)
from app.models.extraction import ContractType, TenderExtractedData, ValueType


class TestResponseAdapterFactory:
    """Test the ResponseAdapterFactory."""

    def test_get_adapter_gemini(self):
        """Test getting Gemini adapter."""
        adapter = ResponseAdapterFactory.get_adapter("gemini")
        assert isinstance(adapter, GeminiResponseAdapter)

    def test_get_adapter_ollama(self):
        """Test getting Ollama adapter."""
        adapter = ResponseAdapterFactory.get_adapter("ollama")
        assert isinstance(adapter, OllamaResponseAdapter)

    def test_get_adapter_openai(self):
        """Test getting OpenAI adapter."""
        adapter = ResponseAdapterFactory.get_adapter("openai")
        assert isinstance(adapter, OpenAIResponseAdapter)

    def test_get_adapter_unsupported(self):
        """Test getting adapter for unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            ResponseAdapterFactory.get_adapter("unsupported")

    def test_register_adapter(self):
        """Test registering new adapter."""

        class TestAdapter(GeminiResponseAdapter):
            pass

        ResponseAdapterFactory.register_adapter("test", TestAdapter)
        adapter = ResponseAdapterFactory.get_adapter("test")
        assert isinstance(adapter, TestAdapter)


class TestGeminiResponseAdapter:
    """Test the GeminiResponseAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = GeminiResponseAdapter()

    def test_adapt_direct_format_success(self):
        """Test successful adaptation of correctly formatted Gemini response."""
        # This is the ideal format that should work directly
        raw_response = {
            "project_title": "Infrastructure Upgrade Project",
            "estimated_value": {
                "amount": Decimal("1000000"),
                "currency": "EUR",
                "value_type": "total",
            },
            "contracting_authority": {
                "name": "Municipal Infrastructure Department",
                "email": "contact@municipality.org",
            },
            "evaluation_criteria": [
                {"criterion": "Technical Solution", "weight_percentage": Decimal("45.0")},
                {"criterion": "Price", "weight_percentage": Decimal("35.0")},
            ],
            "submission_deadline": datetime(2024, 10, 20, 16, 0, 0, tzinfo=UTC),
            "contract_type": "works",
            "cpv_codes": ["45000000-7"],
        }

        result = self.adapter.adapt_response(raw_response)

        assert isinstance(result, TenderExtractedData)
        assert result.project_title == "Infrastructure Upgrade Project"
        assert result.estimated_value.amount == Decimal("1000000")
        assert result.contracting_authority.name == "Municipal Infrastructure Department"
        assert len(result.evaluation_criteria) == 2
        assert result.evaluation_criteria[0].criterion == "Technical Solution"

    def test_adapt_problematic_format_from_error(self):
        """Test adaptation of the problematic format from the error message."""
        # This is the actual format causing issues in the error
        raw_response = {
            "project_title": "Infrastructure Upgrade Project B2",
            "estimated_value": 3750000.0,  # Simple float instead of EstimatedValue dict
            "currency": "EUR",
            "submission_deadline": "2024-10-20T16:00:00Z",
            "contracting_authority": {
                "name": "Municipal Infrastructure Department",
                "contact": "tenders@municipality.org",
            },
            "evaluation_criteria": [
                {
                    "name": "Technical Solution",  # 'name' instead of 'criterion'
                    "weight": 0.45,  # decimal weight instead of percentage
                },
                {"name": "Price Competitiveness", "weight": 0.35},
                {"name": "Project Timeline", "weight": 0.2},
            ],
        }

        result = self.adapter.adapt_response(raw_response)

        assert isinstance(result, TenderExtractedData)
        assert result.project_title == "Infrastructure Upgrade Project B2"

        # Check estimated_value was properly transformed
        assert result.estimated_value is not None
        assert result.estimated_value.amount == Decimal("3750000.0")
        assert result.estimated_value.currency == "EUR"
        assert result.estimated_value.value_type == ValueType.TOTAL

        # Check evaluation_criteria were properly transformed
        assert len(result.evaluation_criteria) == 3
        assert result.evaluation_criteria[0].criterion == "Technical Solution"
        assert result.evaluation_criteria[0].weight_percentage == Decimal("45.0")
        assert result.evaluation_criteria[1].criterion == "Price Competitiveness"
        assert result.evaluation_criteria[1].weight_percentage == Decimal("35.0")
        assert result.evaluation_criteria[2].criterion == "Project Timeline"
        assert result.evaluation_criteria[2].weight_percentage == Decimal("20.0")

    def test_adapt_estimated_value_simple_numeric(self):
        """Test adaptation of simple numeric estimated_value."""
        raw_response = {"estimated_value": 1500000, "currency": "USD"}

        estimated_value = self.adapter._adapt_estimated_value(raw_response)

        assert estimated_value is not None
        assert estimated_value["amount"] == Decimal("1500000")
        assert estimated_value["currency"] == "USD"
        assert estimated_value["value_type"] == ValueType.TOTAL.value

    def test_adapt_estimated_value_missing(self):
        """Test adaptation when estimated_value is missing."""
        raw_response = {}

        estimated_value = self.adapter._adapt_estimated_value(raw_response)
        assert estimated_value is None

    def test_adapt_contracting_authority_simple_string(self):
        """Test adaptation of simple string contracting_authority."""
        raw_response = {"contracting_authority": "Test Authority"}

        authority = self.adapter._adapt_contracting_authority(raw_response)

        assert authority is not None
        assert authority["name"] == "Test Authority"

    def test_adapt_contracting_authority_dict_format(self):
        """Test adaptation of dict format contracting_authority."""
        raw_response = {
            "contracting_authority": {
                "name": "Test Authority",
                "email": "test@authority.org",
                "address": {"city": "Test City"},
            }
        }

        authority = self.adapter._adapt_contracting_authority(raw_response)

        assert authority is not None
        assert authority["name"] == "Test Authority"
        assert authority["email"] == "test@authority.org"
        assert authority["address"]["city"] == "Test City"

    def test_adapt_evaluation_criteria_name_to_criterion(self):
        """Test mapping 'name' field to 'criterion' in evaluation criteria."""
        raw_response = {
            "evaluation_criteria": [
                {
                    "name": "Technical Expertise",
                    "weight": 0.6,
                    "description": "Technical capability assessment",
                },
                {"name": "Cost Effectiveness", "weight": 0.4},
            ]
        }

        criteria = self.adapter._adapt_evaluation_criteria(raw_response)

        assert criteria is not None
        assert len(criteria) == 2
        assert criteria[0]["criterion"] == "Technical Expertise"
        assert criteria[0]["weight_percentage"] == Decimal("60.0")
        assert criteria[0]["description"] == "Technical capability assessment"
        assert criteria[1]["criterion"] == "Cost Effectiveness"
        assert criteria[1]["weight_percentage"] == Decimal("40.0")

    def test_adapt_evaluation_criteria_weight_conversion(self):
        """Test weight conversion from decimal to percentage."""
        raw_response = {
            "evaluation_criteria": [
                {"name": "Test1", "weight": 0.3},  # Should become 30.0
                {"name": "Test2", "weight": 45},  # Should stay 45
                {"name": "Test3", "weight_percentage": 25},  # Should stay 25
            ]
        }

        criteria = self.adapter._adapt_evaluation_criteria(raw_response)

        assert criteria is not None
        assert len(criteria) == 3
        assert criteria[0]["weight_percentage"] == Decimal("30.0")
        assert criteria[1]["weight_percentage"] == Decimal("45")
        assert criteria[2]["weight_percentage"] == Decimal("25")

    def test_adapt_evaluation_criteria_missing_fields(self):
        """Test handling of evaluation criteria with missing required fields."""
        raw_response = {
            "evaluation_criteria": [
                {"weight": 0.5},  # Missing name/criterion
                {"name": "Valid Criterion", "weight": 0.3},  # Valid
                {"criterion": "Also Valid", "weight": 0.2},  # Also valid
            ]
        }

        criteria = self.adapter._adapt_evaluation_criteria(raw_response)

        assert criteria is not None
        assert len(criteria) == 2  # First one should be skipped
        assert criteria[0]["criterion"] == "Valid Criterion"
        assert criteria[1]["criterion"] == "Also Valid"

    def test_safe_decimal_conversion(self):
        """Test safe decimal conversion utility."""
        assert self.adapter._safe_decimal_conversion(100) == Decimal("100")
        assert self.adapter._safe_decimal_conversion("150.5") == Decimal("150.5")
        assert self.adapter._safe_decimal_conversion(None) is None
        assert self.adapter._safe_decimal_conversion("invalid") is None

    def test_safe_enum_conversion(self):
        """Test safe enum conversion utility."""
        result = self.adapter._safe_enum_conversion("works", ContractType)
        assert result == ContractType.WORKS

        result = self.adapter._safe_enum_conversion("SUPPLY", ContractType)
        assert result == ContractType.SUPPLY

        result = self.adapter._safe_enum_conversion("invalid", ContractType)
        assert result == ContractType.SUPPLY  # First enum value as default

        result = self.adapter._safe_enum_conversion(None, ContractType)
        assert result is None

    def test_invalid_response_format(self):
        """Test handling of completely invalid response format."""
        raw_response = {
            "invalid": "data",
            "estimated_value": "not_a_number",
            "evaluation_criteria": "not_a_list",
        }

        # Gemini adapter falls back to transformation logic and handles invalid data gracefully
        result = self.adapter.adapt_response(raw_response)
        assert isinstance(result, TenderExtractedData)
        assert result.project_title is None
        assert result.estimated_value is None  # Invalid value gets filtered out
        assert len(result.evaluation_criteria) == 0  # Invalid criteria gets filtered out


class TestOllamaResponseAdapter:
    """Test the OllamaResponseAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = OllamaResponseAdapter()

    def test_adapt_response_success(self):
        """Test successful adaptation of Ollama response."""
        raw_response = {
            "project_title": "Ollama Test Project",
            "estimated_value": 500000.0,
            "currency": "EUR",
            "contracting_authority": "Ollama Authority",
            "evaluation_criteria": [
                {"name": "Quality", "weight": 0.7},
                {"name": "Price", "weight": 0.3},
            ],
        }

        result = self.adapter.adapt_response(raw_response)

        assert isinstance(result, TenderExtractedData)
        assert result.project_title == "Ollama Test Project"
        assert result.estimated_value.amount == Decimal("500000.0")
        assert result.contracting_authority.name == "Ollama Authority"
        assert len(result.evaluation_criteria) == 2

    def test_invalid_ollama_response(self):
        """Test handling of invalid Ollama response."""
        raw_response = {"completely": "invalid"}

        # Ollama adapter handles invalid data gracefully by creating empty result
        result = self.adapter.adapt_response(raw_response)
        assert isinstance(result, TenderExtractedData)
        assert result.project_title is None
        assert result.estimated_value is None


class TestOpenAIResponseAdapter:
    """Test the OpenAIResponseAdapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = OpenAIResponseAdapter()

    def test_adapt_response_success(self):
        """Test successful adaptation of OpenAI response."""
        raw_response = {
            "project_title": "OpenAI Test Project",
            "estimated_value": {"amount": Decimal("750000"), "currency": "USD"},
            "contracting_authority": {"name": "OpenAI Authority"},
            "evaluation_criteria": [
                {"criterion": "Innovation", "weight_percentage": Decimal("60.0")}
            ],
        }

        result = self.adapter.adapt_response(raw_response)

        assert isinstance(result, TenderExtractedData)
        assert result.project_title == "OpenAI Test Project"
        assert result.estimated_value.amount == Decimal("750000")

    def test_invalid_openai_response(self):
        """Test handling of invalid OpenAI response."""
        raw_response = {"invalid": "format"}

        # OpenAI adapter handles invalid data gracefully by creating result with extra field
        result = self.adapter.adapt_response(raw_response)
        assert isinstance(result, TenderExtractedData)
        assert result.project_title is None
        # The invalid field gets included because of model_config extra="allow"


class TestNPOFormatTransformation:
    """Test NPO format transformation methods that are currently uncovered."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gemini_adapter = GeminiResponseAdapter()
        self.ollama_adapter = OllamaResponseAdapter()

    def test_npo_format_with_direct_project_title(self):
        """Test NPO format transformation with direct project_title."""
        npo_response = {
            "project_title": "Direct NPO Project Title",
            "tender_documents": [],
            "procurement_process": [],
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)

        assert isinstance(result, TenderExtractedData)
        assert result.project_title == "Direct NPO Project Title"

    def test_npo_format_with_tender_documents_title(self):
        """Test extracting project title from tender_documents list."""
        npo_response = {
            "tender_documents": [
                {"title": "", "description": "Empty title doc"},
                {"title": "NPO Infrastructure Project", "description": "Main project document"},
                {"title": "Supporting Document", "description": "Additional info"},
            ],
            "procurement_process": [],
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)

        assert result.project_title == "NPO Infrastructure Project"

    def test_npo_format_with_fallback_title(self):
        """Test fallback to first document title when no meaningful title found."""
        npo_response = {
            "tender_documents": [
                {"title": "", "description": "Empty title"},
                {"title": "Unknown", "description": "Unknown title"},
                {"title": "N/A", "description": "N/A title"},
            ],
            "procurement_process": [],
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)

        assert result.project_title == "NPO Tender Document"  # Fallback from first doc

    def test_npo_format_with_invalid_tender_documents(self):
        """Test handling of invalid tender_documents format."""
        npo_response = {
            "tender_documents": "invalid_format",  # Not a list
            "procurement_process": [],
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)

        assert result.project_title == "NPO Tender Document"

    def test_npo_format_with_empty_tender_documents(self):
        """Test handling of empty tender_documents."""
        npo_response = {"tender_documents": [], "procurement_process": []}

        result = self.gemini_adapter._transform_npo_format(npo_response)

        assert result.project_title is None

    def test_npo_format_with_non_dict_documents(self):
        """Test handling of tender_documents with non-dict elements."""
        npo_response = {
            "tender_documents": [
                "invalid_doc_format",
                {"title": "Valid Document", "description": "This is valid"},
            ],
            "procurement_process": [],
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)

        assert result.project_title == "Valid Document"

    def test_npo_format_transformation_error_handling(self):
        """Test error handling in NPO format transformation."""
        # Test with completely invalid response that causes exception
        invalid_response = None

        with pytest.raises(AttributeError):
            self.gemini_adapter._transform_npo_format(invalid_response)

    def test_npo_format_with_complex_procurement_process(self):
        """Test NPO format with complex procurement_process data."""
        npo_response = {
            "project_title": "Complex NPO Project",
            "tender_documents": [
                {"title": "Technical Specifications", "description": "Detailed tech specs"}
            ],
            "procurement_process": [
                {
                    "phase": "Selection Phase",
                    "description": "Vendor selection criteria and timeline",
                    "requirements": ["Technical capability", "Financial stability"],
                },
                {
                    "phase": "Award Phase",
                    "description": "Final evaluation and contract award",
                    "requirements": ["Best value proposition"],
                },
            ],
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)

        assert result.project_title == "Complex NPO Project"
        assert result.functional_requirements is not None
        assert len(result.functional_requirements) > 0

    def test_safe_enum_conversion_method(self):
        """Test the _safe_enum_conversion utility method."""
        # Test successful enum conversion
        result = self.gemini_adapter._safe_enum_conversion("service", ContractType)
        assert result == ContractType.SERVICE

        # Test case-insensitive conversion
        result = self.gemini_adapter._safe_enum_conversion("SERVICE", ContractType)
        assert result == ContractType.SERVICE

        # Test invalid enum value - returns first enum as default
        result = self.gemini_adapter._safe_enum_conversion("INVALID_TYPE", ContractType)
        assert result == list(ContractType)[0]  # Returns first enum value as default

        # Test non-string value
        result = self.gemini_adapter._safe_enum_conversion(123, ContractType)
        assert result is None

        # Test None value
        result = self.gemini_adapter._safe_enum_conversion(None, ContractType)
        assert result is None

    def test_contracting_authority_adaptation(self):
        """Test contracting authority adaptation with various input formats."""
        # Test with string name
        response = {"contracting_authority": "Test Authority"}
        result = self.gemini_adapter._adapt_contracting_authority(response)
        assert result["name"] == "Test Authority"

        # Test with dict format
        response = {
            "contracting_authority": {
                "name": "Authority Name",
                "contact": "contact@authority.com",
                "address": "123 Authority St",
            }
        }
        result = self.gemini_adapter._adapt_contracting_authority(response)
        assert result["name"] == "Authority Name"
        assert result["contact"] == "contact@authority.com"

        # Test with empty string - should return dict with empty name
        response = {"contracting_authority": ""}
        result = self.gemini_adapter._adapt_contracting_authority(response)
        assert result["name"] == ""

        # Test with missing contracting_authority
        response = {}
        result = self.gemini_adapter._adapt_contracting_authority(response)
        assert result is None

    def test_evaluation_criteria_adaptation(self):
        """Test evaluation criteria adaptation with weight calculations."""
        # Test with decimal weights (should convert to percentage)
        response = {
            "evaluation_criteria": [
                {"criterion": "Technical", "weight": 0.6},
                {"criterion": "Price", "weight": 0.4},
            ]
        }
        result = self.gemini_adapter._adapt_evaluation_criteria(response)
        assert len(result) == 2
        assert result[0]["weight_percentage"] == 60.0
        assert result[1]["weight_percentage"] == 40.0

        # Test with percentage weights (should remain unchanged)
        response = {
            "evaluation_criteria": [
                {"criterion": "Quality", "weight_percentage": 70},
                {"criterion": "Cost", "weight_percentage": 30},
            ]
        }
        result = self.gemini_adapter._adapt_evaluation_criteria(response)
        assert len(result) == 2
        assert result[0]["weight_percentage"] == 70
        assert result[1]["weight_percentage"] == 30

        # Test with mixed weight formats
        response = {
            "evaluation_criteria": [
                {"criterion": "Technical", "weight": 0.5},  # decimal
                {"name": "Price", "weight_percentage": 50},  # percentage
            ]
        }
        result = self.gemini_adapter._adapt_evaluation_criteria(response)
        assert len(result) == 2
        assert result[0]["criterion"] == "Technical"
        assert result[0]["weight_percentage"] == 50.0
        assert result[1]["criterion"] == "Price"
        assert result[1]["weight_percentage"] == 50

        # Test with invalid data - should return None based on the warning message
        response = {"evaluation_criteria": "invalid"}
        result = self.gemini_adapter._adapt_evaluation_criteria(response)
        assert result is None

    def test_standard_format_error_paths(self):
        """Test error handling in standard format adaptation."""
        # Test with malformed estimated_value
        response = {"project_title": "Test Project", "estimated_value": "invalid_format"}
        result = self.gemini_adapter.adapt_response(response)
        assert result.project_title == "Test Project"
        assert result.estimated_value is None

        # Test with invalid contracting_authority
        response = {"project_title": "Test Project", "contracting_authority": 123}  # Invalid type
        result = self.gemini_adapter.adapt_response(response)
        assert result.project_title == "Test Project"

    def test_ollama_npo_format_handling(self):
        """Test that Ollama adapter also handles NPO format correctly."""
        npo_response = {
            "tender_documents": [
                {"title": "Ollama NPO Project", "description": "Project via Ollama"}
            ],
            "procurement_process": [],
        }

        result = self.ollama_adapter._transform_npo_format(npo_response)
        assert result.project_title == "Ollama NPO Project"

    def test_additional_coverage_paths(self):
        """Test additional code paths to reach 85% coverage."""
        # Test adapt_response with completely empty response
        result = self.gemini_adapter.adapt_response({})
        assert isinstance(result, TenderExtractedData)
        assert result.project_title is None

    def test_npo_procurement_phases_processing(self):
        """Test procurement phases extraction from NPO format."""
        npo_response = {
            "procurement_process": [
                {
                    "phase": "Preparation",
                    "title": "Document Preparation",
                    "description": "Prepare tender documents",
                    "deadline": "2024-12-31",
                    "status": "active",
                },
                {
                    "phase": "Evaluation",
                    "title": "Bid Evaluation",
                    "description": "Evaluate submitted bids",
                },
            ]
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)
        assert isinstance(result, TenderExtractedData)
        assert len(result.procurement_phases) == 2

        phase1 = result.procurement_phases[0]
        assert phase1.phase == "Preparation"
        assert phase1.title == "Document Preparation"
        assert phase1.description == "Prepare tender documents"
        assert phase1.deadline == "2024-12-31"
        assert phase1.status == "active"

        phase2 = result.procurement_phases[1]
        assert phase2.phase == "Evaluation"
        assert phase2.title == "Bid Evaluation"

    def test_npo_complaint_procedure_processing(self):
        """Test complaint procedure extraction from NPO format."""
        npo_response = {
            "complaint_procedure": {
                "description": "File complaints within 10 business days",
                "deadline": "10 business days",
                "method": "Email or postal mail",
                "contact_info": "complaints@authority.gov",
                "authority": "Public Procurement Authority",
            }
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)
        assert isinstance(result, TenderExtractedData)
        assert result.complaint_procedure is not None

        complaint = result.complaint_procedure
        assert complaint.description == "File complaints within 10 business days"
        assert complaint.deadline == "10 business days"
        assert complaint.method == "Email or postal mail"
        assert complaint.contact_info == "complaints@authority.gov"
        assert complaint.authority == "Public Procurement Authority"

    def test_npo_document_structure_processing(self):
        """Test document structure extraction from NPO format."""
        npo_response = {
            "tender_documents": [
                {
                    "title": "Technical Specifications",
                    "description": "Detailed technical requirements",
                    "document_type": "specification",
                    "section": "Part A",
                    "pages": ["1-15", "20-25"],
                },
                {
                    "title": "Contract Conditions",
                    "description": "General contract terms",
                    "document_type": "contract",
                },
            ]
        }

        result = self.gemini_adapter._transform_npo_format(npo_response)
        assert isinstance(result, TenderExtractedData)
        assert len(result.document_structure) == 2

        doc1 = result.document_structure[0]
        assert doc1.title == "Technical Specifications"
        assert doc1.description == "Detailed technical requirements"
        assert doc1.document_type == "specification"
        assert doc1.section == "Part A"
        assert doc1.page_references == ["1-15", "20-25"]

        doc2 = result.document_structure[1]
        assert doc2.title == "Contract Conditions"
        assert doc2.description == "General contract terms"
        assert doc2.document_type == "contract"

    def test_contract_type_enum_conversion_coverage(self):
        """Test contract_type enum conversion in standard format."""
        raw_response = {"contract_type": "service"}  # String that should be converted to enum

        # Test enum conversion through the main adapter method
        result = self.gemini_adapter.adapt_response(raw_response)
        assert isinstance(result, TenderExtractedData)
        assert result.contract_type == ContractType.SERVICE

    def test_edge_case_response_formats(self):
        """Test edge cases in response format detection."""
        # Test response with neither NPO format nor standard format
        response = {"unknown_field": "unknown_value"}
        result = self.gemini_adapter.adapt_response(response)
        assert isinstance(result, TenderExtractedData)

        # Test response with mixed formats
        response = {
            "project_title": "Mixed Format Project",
            "tender_documents": [],  # NPO elements
            "estimated_value": "1000000",  # Standard elements
        }
        result = self.gemini_adapter.adapt_response(response)
        assert result.project_title == "Mixed Format Project"

    def test_enum_conversion_error_handling(self):
        """Test enum conversion with invalid values that cause exceptions."""
        from app.models.extraction import ContractType

        # Test with None and invalid objects
        assert self.gemini_adapter._safe_enum_conversion(None, ContractType) is None
        assert (
            self.gemini_adapter._safe_enum_conversion({"invalid": "object"}, ContractType) is None
        )
        assert self.gemini_adapter._safe_enum_conversion(["list"], ContractType) is None

        # Test with an object that causes AttributeError when .lower() is called
        class BadObject:
            def __str__(self):
                return "bad_object"

            def lower(self):
                raise AttributeError("No lower method")

        result = self.gemini_adapter._safe_enum_conversion(BadObject(), ContractType)
        assert result is None

    def test_npo_evaluation_criteria_with_logging(self):
        """Test NPO evaluation criteria adaptation with logging branch coverage."""
        npo_response = {
            "tender_documents": [
                {
                    "title": "Highway Construction",
                    "evaluation_criteria": [
                        {"criterion": "Technical quality", "weight": 60},
                        {"criterion": "Financial offer", "weight": 40},
                    ],
                }
            ]
        }

        result = self.gemini_adapter.adapt_response(npo_response)

        assert isinstance(result, TenderExtractedData)
        assert len(result.evaluation_criteria) == 2
        assert result.evaluation_criteria[0].criterion == "Technical quality"
        assert result.evaluation_criteria[0].weight_percentage == 60
        assert result.evaluation_criteria[1].criterion == "Financial offer"
        assert result.evaluation_criteria[1].weight_percentage == 40

    def test_npo_complaint_procedure_string_format(self):
        """Test NPO complaint procedure as simple string (lines 212-217)."""
        npo_response = {
            "tender_documents": [{"title": "Public Works Tender"}],
            "complaint_procedure": "Submit complaints to procurement@authority.gov within 5 days",
        }

        result = self.gemini_adapter.adapt_response(npo_response)

        assert isinstance(result, TenderExtractedData)
        # Should map complaint procedure string to submission_requirements
        assert result.submission_requirements is not None
        assert len(result.submission_requirements.documents_required) == 1
        assert "Complaint procedure:" in result.submission_requirements.documents_required[0]
        assert (
            "Submit complaints to procurement@authority.gov"
            in result.submission_requirements.documents_required[0]
        )

    def test_npo_exclusion_and_selection_criteria_strings(self):
        """Test handling exclusion_grounds and selection_criteria as strings."""
        npo_response = {
            "tender_documents": [{"title": "Eligibility Requirements"}],
            "exclusion_grounds": "No criminal record required",  # Single string
            "selection_criteria": "Minimum 5 years experience",  # Single string
            "application_conditions": "Must be registered in EU",  # Single string
        }

        result = self.gemini_adapter.adapt_response(npo_response)

        assert isinstance(result, TenderExtractedData)
        assert len(result.exclusion_grounds) == 1
        assert result.exclusion_grounds[0] == "No criminal record required"
        assert len(result.selection_criteria) == 1
        assert result.selection_criteria[0] == "Minimum 5 years experience"
        assert len(result.application_conditions) == 1
        assert result.application_conditions[0] == "Must be registered in EU"

    def test_error_paths_and_edge_cases(self):
        """Test various error paths and edge cases for coverage."""
        # Test with malformed tender_documents
        malformed_response = {
            "tender_documents": "not_a_list",  # Should be list but is string
            "project_title": "Test Project",
        }

        result = self.gemini_adapter.adapt_response(malformed_response)
        assert isinstance(result, TenderExtractedData)
        assert result.project_title == "Test Project"

        # Test with empty but valid structures
        empty_response = {
            "tender_documents": [],
            "procurement_process": [],
            "evaluation_criteria": [],
            "contracting_authority": {},
        }

        result = self.gemini_adapter.adapt_response(empty_response)
        assert isinstance(result, TenderExtractedData)
        assert len(result.document_structure) == 0
        assert len(result.procurement_phases) == 0
        assert len(result.evaluation_criteria) == 0


class TestRealWorldScenarios:
    """Test real-world scenarios and edge cases."""

    def test_gemini_with_mixed_data_formats(self):
        """Test Gemini adapter with mixed data formats from real API responses."""
        adapter = GeminiResponseAdapter()

        # Simulate the exact response format from the error
        raw_response = {
            "project_title": "Infrastructure Upgrade Project B2",
            "estimated_value": 3750000,  # float
            "currency": "EUR",
            "submission_deadline": "2024-10-20T16:00:00Z",
            "contracting_authority": {
                "name": "Municipal Infrastructure Department",
                "contact": "tenders@municipality.org",
            },
            "evaluation_criteria": [
                {"name": "Technical Solution", "weight": 0.45},
                {"name": "Price Competitiveness", "weight": 0.35},
                {"name": "Project Timeline", "weight": 0.2},
            ],
            "confidence_scores": {
                "project_title": 0.91,
                "estimated_value": 0.85,
                "submission_deadline": 0.94,
                "contracting_authority": 0.89,
                "evaluation_criteria": 0.82,
            },
            "extraction_metadata": {
                "processing_time": 3.1,
                "confidence_overall": 0.88,
                "flags": ["complex_formatting", "multiple_sections"],
            },
        }

        result = adapter.adapt_response(raw_response)

        # Verify all transformations worked correctly
        assert result.project_title == "Infrastructure Upgrade Project B2"
        assert result.estimated_value.amount == Decimal("3750000")
        assert result.estimated_value.currency == "EUR"
        assert len(result.evaluation_criteria) == 3
        assert all(criterion.criterion is not None for criterion in result.evaluation_criteria)
        assert all(
            criterion.weight_percentage is not None for criterion in result.evaluation_criteria
        )

    def test_empty_and_null_values(self):
        """Test handling of empty and null values."""
        adapter = GeminiResponseAdapter()

        raw_response = {
            "project_title": None,
            "estimated_value": None,
            "contracting_authority": None,
            "evaluation_criteria": [],
            "cpv_codes": [],
        }

        result = adapter.adapt_response(raw_response)

        assert result.project_title is None
        assert result.estimated_value is None
        assert result.contracting_authority is None
        assert len(result.evaluation_criteria) == 0
        assert len(result.cpv_codes) == 0

    def test_partial_data_extraction(self):
        """Test adaptation with only partial data available."""
        adapter = GeminiResponseAdapter()

        raw_response = {
            "project_title": "Partial Data Project",
            "estimated_value": 1000000.0,
            "currency": "EUR"
            # Missing many other fields
        }

        result = adapter.adapt_response(raw_response)

        assert result.project_title == "Partial Data Project"
        assert result.estimated_value.amount == Decimal("1000000.0")
        assert result.contracting_authority is None
        assert len(result.evaluation_criteria) == 0
