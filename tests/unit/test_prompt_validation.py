from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

from app.utils.prompt_builder import get_prompt_builder


class TestPromptValidation:
    """Test prompt validation and golden dataset verification."""

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
    async def test_golden_dataset_validation(self, prompt_validation_dataset):
        """Test prompt building accuracy against golden dataset."""
        prompt_builder = get_prompt_builder()
        results = []

        for test_case in prompt_validation_dataset:
            # Build prompt
            prompt_result = prompt_builder.build_prompt(
                document_content=test_case["document_text"], config_name="default"
            )

            # Validate prompt structure
            validation = prompt_builder.validate_prompt_build(prompt_result)

            # Test that expected fields are mentioned in prompt
            prompt_text = prompt_result["prompt"]
            field_mentions = 0
            total_expected_fields = len(test_case["expected_fields"])

            for field_path in test_case["expected_fields"].keys():
                # Check if field name is mentioned in prompt
                field_name = field_path.split(".")[-1]
                if field_name.lower() in prompt_text.lower():
                    field_mentions += 1

            field_coverage = (
                field_mentions / total_expected_fields if total_expected_fields > 0 else 0
            )

            results.append(
                {
                    "is_valid": validation["is_valid"],
                    "field_coverage": field_coverage,
                    "errors": validation["errors"],
                }
            )

        # Calculate overall metrics
        valid_prompts = sum(1 for r in results if r["is_valid"])
        avg_field_coverage = sum(r["field_coverage"] for r in results) / len(results)

        # Assert minimum thresholds
        assert (
            valid_prompts / len(results) >= 0.9
        ), f"Prompt validation rate {valid_prompts/len(results):.2f} below threshold 0.9"
        assert (
            avg_field_coverage >= 0.7
        ), f"Average field coverage {avg_field_coverage:.2f} below threshold 0.7"

        # Log detailed results
        for i, result in enumerate(results):
            print(
                f"Test case {i+1}: Valid = {result['is_valid']}, Field coverage = {result['field_coverage']:.2f}"
            )
            if result["errors"]:
                print(f"  Errors: {result['errors']}")

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
