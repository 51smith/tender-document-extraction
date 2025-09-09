import pytest
from unittest.mock import AsyncMock, patch
from typing import Dict, Any

from app.utils.prompt_builder import get_prompt_builder
from app.services.extraction_worker import ExtractionService
from app.models.extraction import DocumentExtractionRequest


class TestPromptValidation:
    """Test prompt validation and golden dataset verification."""

    @pytest.fixture
    def extraction_service(self, mock_gemini_client):
        """Create extraction service with mocked Gemini client."""
        with patch(
            "app.services.extraction_worker.get_gemini_client", return_value=mock_gemini_client
        ):
            return ExtractionService()

    @pytest.mark.asyncio
    async def test_prompt_building_basic(self):
        """Test basic prompt building functionality."""
        prompt_builder = get_prompt_builder()

        document_content = "Sample tender document content"

        result = prompt_builder.build_prompt(
            document_content=document_content, config_name="default"
        )

        assert "prompt" in result
        assert "config" in result
        assert "template" in result
        assert "hash" in result
        assert "metadata" in result

        # Check that document content is included
        assert document_content in result["prompt"]

        # Check for required sections
        assert "DOCUMENT TO ANALYZE:" in result["prompt"]
        assert "EXPECTED OUTPUT SCHEMA:" in result["prompt"]

    @pytest.mark.asyncio
    async def test_template_inheritance(self):
        """Test template inheritance system."""
        prompt_builder = get_prompt_builder()

        # Test that tender_extraction template inherits from base
        template_info = prompt_builder.get_template_info("tender_extraction")

        assert "name" in template_info
        assert template_info["name"] == "tender_extraction"

    @pytest.mark.asyncio
    async def test_prompt_validation(self):
        """Test prompt validation system."""
        prompt_builder = get_prompt_builder()

        document_content = "Test document"
        prompt_result = prompt_builder.build_prompt(document_content, "default")

        validation = prompt_builder.validate_prompt_build(prompt_result)

        assert "is_valid" in validation
        assert "errors" in validation
        assert "warnings" in validation
        assert "metrics" in validation

        # Should be valid for basic test
        assert validation["is_valid"] is True

    @pytest.mark.asyncio
    async def test_golden_dataset_validation(self, prompt_validation_dataset, extraction_service):
        """Test extraction accuracy against golden dataset."""
        results = []

        for test_case in prompt_validation_dataset:
            # Create extraction request
            request = DocumentExtractionRequest(
                filename="test_document.txt", content_type="text/plain"
            )

            # Mock document processing
            with patch("app.services.extraction_worker.get_document_processor") as mock_processor:
                mock_doc_processor = mock_processor.return_value
                mock_doc_processor.process_document.return_value.text = test_case["document_text"]
                mock_doc_processor.process_document.return_value.images = []
                mock_doc_processor.process_document.return_value.tables = []
                mock_doc_processor.process_document.return_value.metadata = {}
                mock_doc_processor.process_document.return_value.content_hash = "test_hash"
                mock_doc_processor.process_document.return_value.file_type = "text/plain"
                mock_doc_processor.process_document.return_value.file_size = 1000

                mock_doc_processor.validate_document.return_value = {"is_valid": True, "errors": []}
                mock_doc_processor.get_multimodal_content.return_value = [
                    test_case["document_text"]
                ]

                # Mock Gemini response to return expected data
                mock_response = self._create_mock_response_from_expected(
                    test_case["expected_fields"]
                )

                with patch.object(
                    extraction_service.gemini_client, "generate_content", return_value=mock_response
                ):
                    # Extract data
                    result = await extraction_service.extract_from_document(
                        test_case["document_text"].encode(), request
                    )

                    # Validate against expected fields
                    validation_result = self._validate_extraction_result(result, test_case)
                    results.append(validation_result)

        # Calculate overall accuracy
        accuracy = sum(r["accuracy"] for r in results) / len(results)

        # Assert minimum accuracy threshold
        assert accuracy >= 0.8, f"Golden dataset accuracy {accuracy:.2f} below threshold 0.8"

        # Log detailed results
        for i, result in enumerate(results):
            print(f"Test case {i+1}: Accuracy = {result['accuracy']:.2f}")
            if result["errors"]:
                print(f"  Errors: {result['errors']}")

    def _create_mock_response_from_expected(
        self, expected_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a mock Gemini response based on expected fields."""
        extracted_data = {}

        # Handle nested field paths like "contracting_authority.name"
        for field_path, value in expected_fields.items():
            self._set_nested_field(extracted_data, field_path, value)

        return {
            "extracted_data": extracted_data,
            "confidence_scores": {"overall": 0.9},
            "extraction_notes": {
                "ambiguities": [],
                "assumptions": [],
                "missing_information": [],
                "recommendations": [],
            },
            "processing_metadata": {
                "document_type": "text/plain",
                "language": "en",
                "extraction_complexity": "simple",
            },
            "_metadata": {
                "model": "gemini-2.5-pro",
                "processing_time": 1.5,
                "estimated_tokens": 800,
                "actual_tokens": 750,
            },
        }

    def _set_nested_field(self, data: Dict[str, Any], field_path: str, value: Any):
        """Set a nested field in a dictionary using dot notation."""
        parts = field_path.split(".")
        current = data

        # Navigate to the parent of the target field
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the final field
        current[parts[-1]] = value

    def _validate_extraction_result(self, result, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extraction result against test case expectations."""
        errors = []
        correct_fields = 0
        total_fields = 0

        expected_fields = test_case["expected_fields"]

        for field_path, expected_value in expected_fields.items():
            total_fields += 1

            # Get actual value using field path
            actual_value = self._get_nested_field(result.extracted_data.model_dump(), field_path)

            if actual_value is None:
                errors.append(f"Missing field: {field_path}")
            elif self._values_match(actual_value, expected_value):
                correct_fields += 1
            else:
                errors.append(
                    f"Field mismatch {field_path}: expected {expected_value}, got {actual_value}"
                )

        accuracy = correct_fields / total_fields if total_fields > 0 else 0

        return {
            "accuracy": accuracy,
            "correct_fields": correct_fields,
            "total_fields": total_fields,
            "errors": errors,
        }

    def _get_nested_field(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get a nested field from a dictionary using dot notation."""
        parts = field_path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    def _values_match(self, actual: Any, expected: Any) -> bool:
        """Check if actual and expected values match (with type tolerance)."""
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            return abs(float(actual) - float(expected)) < 0.01
        elif isinstance(expected, str) and isinstance(actual, str):
            return actual.lower().strip() == expected.lower().strip()
        elif isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                return False
            return all(self._values_match(a, e) for a, e in zip(actual, expected))
        else:
            return actual == expected

    @pytest.mark.asyncio
    async def test_prompt_performance_metrics(self):
        """Test prompt performance metrics collection."""
        prompt_builder = get_prompt_builder()

        # Build prompts with different complexities
        simple_doc = "Simple tender: Project X, €1000"
        complex_doc = "A" * 10000  # Large document

        simple_result = prompt_builder.build_prompt(simple_doc, "default")
        complex_result = prompt_builder.build_prompt(complex_doc, "default")

        # Validate both prompts
        simple_validation = prompt_builder.validate_prompt_build(simple_result)
        complex_validation = prompt_builder.validate_prompt_build(complex_result)

        # Check metrics are collected
        assert "metrics" in simple_validation
        assert "metrics" in complex_validation

        # Complex document should have longer prompt
        assert (
            complex_validation["metrics"]["prompt_length"]
            > simple_validation["metrics"]["prompt_length"]
        )

    @pytest.mark.asyncio
    async def test_prompt_template_versions(self):
        """Test prompt template versioning and tracking."""
        prompt_builder = get_prompt_builder()

        available_templates = prompt_builder.get_available_templates()

        assert len(available_templates) > 0

        for template_name in available_templates:
            template_info = prompt_builder.get_template_info(template_name)

            assert "name" in template_info
            assert template_info["name"] == template_name

            # Check that we can build prompts with each template
            if template_name != "base":  # Base is abstract
                result = prompt_builder.build_prompt(
                    "Test document", template_override=template_name
                )
                assert result["prompt"] is not None
