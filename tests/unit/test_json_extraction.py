"""
Tests for JSON extraction from LLM responses with markdown code blocks.

This module tests the _extract_json_from_markdown method that handles
various response formats from different LLM providers.
"""


from app.services.llm_service import BaseLLMService


class TestLLMService(BaseLLMService):
    """Test implementation of BaseLLMService for testing JSON extraction."""

    def __init__(self):
        pass

    def get_provider_name(self):
        return "test"

    def get_provider_info(self):
        return {}

    async def health_check(self):
        return True

    async def _generate_content_impl(self, *args, **kwargs):
        return {}


class TestJSONExtraction:
    """Test JSON extraction from various response formats."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = TestLLMService()

    def test_extract_json_code_block(self):
        """Test extraction from ```json code block."""
        response = """Here is the result:

```json
{
    "project_title": "Test Project",
    "estimated_value": 1000000
}
```

This is the extracted data."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is not None
        assert "project_title" in json_text
        assert "Test Project" in json_text

    def test_extract_plain_code_block(self):
        """Test extraction from ``` code block (the problematic case)."""
        response = """Here is the extracted information in JSON format:

```
{
    "tender_documents": [
        {
            "title": "2.1. Tender Documents",
            "description": "The tender documents will be available."
        }
    ],
    "procurement_process": [
        {
            "title": "Fase 1: Beoordeling",
            "description": "The evaluation will take place."
        }
    ]
}
```

Please note that this is a consolidated extraction result."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is not None
        assert "tender_documents" in json_text
        assert "procurement_process" in json_text

        # Should be valid JSON
        import json

        parsed = json.loads(json_text)
        assert "tender_documents" in parsed
        assert len(parsed["tender_documents"]) == 1

    def test_extract_json_after_text(self):
        """Test extraction when JSON appears after explanatory text."""
        response = """Based on the document analysis, here are the extracted details:

{
    "project_title": "Infrastructure Project",
    "estimated_value": 2500000,
    "currency": "EUR",
    "contracting_authority": {
        "name": "Municipal Department"
    }
}

Please review this information for accuracy."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is not None
        assert "project_title" in json_text
        assert "Infrastructure Project" in json_text

        # Test that it stops before the explanatory text
        assert "Please review" not in json_text

    def test_extract_array_json(self):
        """Test extraction when JSON is an array."""
        response = """The evaluation criteria are:

```
[
    {
        "criterion": "Technical Solution",
        "weight_percentage": 45.0
    },
    {
        "criterion": "Price",
        "weight_percentage": 35.0
    }
]
```

These are the main criteria."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is not None
        assert json_text.strip().startswith("[")
        assert "Technical Solution" in json_text

        # Should be valid JSON
        import json

        parsed = json.loads(json_text)
        assert len(parsed) == 2
        assert parsed[0]["criterion"] == "Technical Solution"

    def test_no_json_content(self):
        """Test when there's no JSON content in the response."""
        response = """This is just a plain text response without any JSON data.

        There are no code blocks or structured data here.

        Just regular explanatory text."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is None

    def test_malformed_code_block(self):
        """Test handling of malformed code blocks."""
        response = """Here's some data:

```
This is not JSON content
Just some random text in a code block
```

No valid JSON here."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is None  # Should not extract non-JSON content

    def test_multiple_code_blocks(self):
        """Test when there are multiple code blocks, should pick the JSON one."""
        response = """Here are some examples:

First, some shell commands:
```bash
curl -X GET http://example.com
```

And here's the JSON data:
```
{
    "result": "success",
    "data": {
        "items": ["a", "b", "c"]
    }
}
```

That's the extracted information."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is not None
        assert "result" in json_text
        assert "success" in json_text
        assert "curl" not in json_text  # Should not pick the bash block

    def test_json_with_explanatory_cutoff(self):
        """Test that extraction stops at explanatory text markers."""
        response = """The analysis results:

{
    "project_title": "Road Construction",
    "estimated_value": 5000000
}

Please note that this data was extracted automatically and may require verification."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is not None
        assert "project_title" in json_text
        assert "Road Construction" in json_text
        assert "Please note" not in json_text  # Should stop before this

    def test_complex_nested_json(self):
        """Test extraction of complex nested JSON structure."""
        response = """Analysis complete:

```
{
    "tender_info": {
        "project_title": "Complex Infrastructure Project",
        "estimated_value": {
            "amount": 10000000,
            "currency": "EUR"
        },
        "evaluation_criteria": [
            {
                "name": "Technical Expertise",
                "weight": 0.6,
                "sub_criteria": [
                    {"item": "Experience", "points": 30},
                    {"item": "Qualifications", "points": 20}
                ]
            }
        ]
    },
    "metadata": {
        "extraction_date": "2024-01-15",
        "confidence": 0.89
    }
}
```

This represents the complete tender analysis."""

        json_text = self.service._extract_json_from_markdown(response)
        assert json_text is not None

        # Should be valid complex JSON
        import json

        parsed = json.loads(json_text)
        assert "tender_info" in parsed
        assert "metadata" in parsed
        assert parsed["tender_info"]["project_title"] == "Complex Infrastructure Project"
        assert len(parsed["tender_info"]["evaluation_criteria"]) == 1
        assert len(parsed["tender_info"]["evaluation_criteria"][0]["sub_criteria"]) == 2
