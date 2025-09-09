"""
Unit tests for ResponseAdapter with exact NPO response format.

This test module validates the transformation of the exact NPO response format
that was failing in the real job: 77625623-6502-4d22-91e7-d84b23767203
"""


import pytest

from app.adapters.response_adapter import GeminiResponseAdapter
from app.models.extraction import TenderExtractedData


class TestNPOResponseAdapter:
    """Test ResponseAdapter with real NPO response format."""

    @pytest.fixture()
    def npo_raw_response(self):
        """Exact raw_response format from failing NPO job 77625623-6502-4d22-91e7-d84b23767203."""
        return {
            "tender_documents": [
                {
                    "title": "2.1. Tender Documents",
                    "description": (
                        "The tender documents consist of various sections including "
                        "the assignment description, selection criteria, exclusion grounds, "
                        "and application conditions."
                    ),
                }
            ],
            "procurement_process": [
                {
                    "phase": "Selection Phase",
                    "description": (
                        "The selection phase involves evaluating candidates based on "
                        "predefined criteria and exclusion grounds."
                    ),
                    "deadline": "To be specified in the tender documents",
                },
                {
                    "phase": "Award Phase",
                    "description": (
                        "The award phase involves the final evaluation and selection "
                        "of the winning tender."
                    ),
                    "deadline": "To be specified after selection phase",
                },
            ],
            "evaluation_criteria": [
                {
                    "name": "Technical Capability",
                    "description": "Assessment of technical skills and experience",
                    "weightage": 60.0,
                },
                {
                    "name": "Financial Sustainability",
                    "description": "Evaluation of financial stability and sustainability",
                    "weightage": 40.0,
                },
            ],
            "complaint_procedure": {
                "description": "Candidates can file complaints according to the Dutch procurement law",
                "deadline": "Within 10 days of notification",
                "method": "Submit written complaint to the contracting authority",
            },
        }

    @pytest.fixture()
    def response_adapter(self):
        """GeminiResponseAdapter instance for testing."""
        return GeminiResponseAdapter()

    def test_npo_format_detection(self, response_adapter, npo_raw_response):
        """Test that NPO alternative format is correctly detected."""
        # The adapter should detect alternative format and not attempt direct construction
        result = response_adapter.adapt_response(npo_raw_response)

        # Verify that transformation worked and we got a TenderExtractedData object
        assert isinstance(result, TenderExtractedData)

    def test_project_title_extraction(self, response_adapter, npo_raw_response):
        """Test project_title extraction from tender_documents."""
        result = response_adapter.adapt_response(npo_raw_response)

        # Should extract title from first tender document
        assert result.project_title == "2.1. Tender Documents"

    def test_contracting_authority_extraction(self, response_adapter, npo_raw_response):
        """Test contracting_authority extraction for NPO format."""
        result = response_adapter.adapt_response(npo_raw_response)

        # Should detect NPO format and set default contracting authority
        assert result.contracting_authority is not None
        assert result.contracting_authority.name == "Nederlandse Publieke Omroep (NPO)"

    def test_evaluation_criteria_transformation(self, response_adapter, npo_raw_response):
        """Test evaluation_criteria transformation with 'weightage' field."""
        result = response_adapter.adapt_response(npo_raw_response)

        # Should transform evaluation criteria with weightage to weight_percentage
        assert result.evaluation_criteria is not None
        assert len(result.evaluation_criteria) == 2

        # Check first criterion
        first_criterion = result.evaluation_criteria[0]
        assert first_criterion.criterion == "Technical Capability"
        assert first_criterion.description == "Assessment of technical skills and experience"
        assert float(first_criterion.weight_percentage) == 60.0

        # Check second criterion
        second_criterion = result.evaluation_criteria[1]
        assert second_criterion.criterion == "Financial Sustainability"
        assert (
            second_criterion.description == "Evaluation of financial stability and sustainability"
        )
        assert float(second_criterion.weight_percentage) == 40.0

    def test_functional_requirements_extraction(self, response_adapter, npo_raw_response):
        """Test functional_requirements extraction from tender_documents and procurement_process."""
        result = response_adapter.adapt_response(npo_raw_response)

        # Should extract functional requirements from documents and process
        assert result.functional_requirements is not None
        assert len(result.functional_requirements) > 0

        # Should include data from tender_documents
        tender_req = (
            "2.1. Tender Documents: The tender documents consist of various sections "
            "including the assignment description, selection criteria, exclusion "
            "grounds, and application conditions."
        )
        assert tender_req in result.functional_requirements

        # Should include data from procurement_process
        process_reqs = [req for req in result.functional_requirements if req.startswith("Process:")]
        assert len(process_reqs) == 2  # Two process phases

        selection_req = (
            "Process: Selection Phase - The selection phase involves evaluating "
            "candidates based on predefined criteria and exclusion grounds."
        )
        award_req = (
            "Process: Award Phase - The award phase involves the final evaluation "
            "and selection of the winning tender."
        )

        assert selection_req in result.functional_requirements
        assert award_req in result.functional_requirements

    def test_submission_requirements_from_complaint_procedure(
        self, response_adapter, npo_raw_response
    ):
        """Test submission_requirements mapping from complaint_procedure."""
        result = response_adapter.adapt_response(npo_raw_response)

        # Should map complaint_procedure to submission_requirements
        assert result.submission_requirements is not None
        assert result.submission_requirements.documents_required is not None
        assert len(result.submission_requirements.documents_required) == 1

        complaint_doc = result.submission_requirements.documents_required[0]
        assert (
            complaint_doc == "Complaint: Candidates can file complaints according to the Dutch "
            "procurement law"
        )

        # Check submission method
        expected_method = "Method: Submit written complaint to the contracting authority | Deadline: Within 10 days of notification"
        assert result.submission_requirements.submission_method == expected_method

    def test_all_fields_populated(self, response_adapter, npo_raw_response):
        """Test that transformation results in populated fields, not null values."""
        result = response_adapter.adapt_response(npo_raw_response)

        # Verify key fields are not null (the original issue)
        assert result.project_title is not None
        assert result.project_title != ""

        assert result.contracting_authority is not None
        assert result.contracting_authority.name is not None
        assert result.contracting_authority.name != ""

        assert result.evaluation_criteria is not None
        assert len(result.evaluation_criteria) > 0

        assert result.functional_requirements is not None
        assert len(result.functional_requirements) > 0

        assert result.submission_requirements is not None

    def test_no_null_values_in_extracted_data(self, response_adapter, npo_raw_response):
        """Test that important fields are not null - addressing the core issue."""
        result = response_adapter.adapt_response(npo_raw_response)

        # Convert to dict to check for null values
        result_dict = result.model_dump()

        # These fields should not be null after transformation
        critical_fields = [
            "project_title",
            "contracting_authority",
            "evaluation_criteria",
            "functional_requirements",
            "submission_requirements",
        ]

        for field in critical_fields:
            assert (
                result_dict[field] is not None
            ), f"Field {field} should not be null after NPO transformation"

        # Specifically check nested structures
        assert result_dict["contracting_authority"]["name"] is not None
        assert len(result_dict["evaluation_criteria"]) > 0
        assert len(result_dict["functional_requirements"]) > 0

    def test_npo_format_with_missing_fields(self, response_adapter):
        """Test NPO format handling when some fields are missing."""
        partial_response = {
            "tender_documents": [{"title": "Test Document", "description": "Test description"}],
            "evaluation_criteria": [{"name": "Quality", "weightage": 100.0}]
            # Missing procurement_process and complaint_procedure
        }

        result = response_adapter.adapt_response(partial_response)

        # Should still work with partial data
        assert result.project_title == "Test Document"
        assert (
            result.contracting_authority.name == "Nederlandse Publieke Omroep (NPO)"
        )  # Default for NPO format
        assert len(result.evaluation_criteria) == 1
        assert result.evaluation_criteria[0].weight_percentage == 100.0

    def test_weightage_vs_weight_handling(self, response_adapter):
        """Test that both 'weightage' and 'weight' fields are handled correctly."""
        # Test with 'weightage' (NPO format)
        npo_criteria = {"evaluation_criteria": [{"name": "Test Criterion", "weightage": 75.0}]}

        result = response_adapter._adapt_evaluation_criteria(npo_criteria)
        assert len(result) == 1
        assert float(result[0]["weight_percentage"]) == 75.0

        # Test with standard 'weight' field
        standard_criteria = {
            "evaluation_criteria": [{"name": "Test Criterion", "weight": 0.75}]  # Decimal format
        }

        result = response_adapter._adapt_evaluation_criteria(standard_criteria)
        assert len(result) == 1
        assert float(result[0]["weight_percentage"]) == 75.0  # Should convert to percentage
