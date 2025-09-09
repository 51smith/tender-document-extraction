# Feature: Multi-LLM Provider Architecture

**Feature ID**: F-2025-001
**Status**: In Development
**Priority**: High
**Assignee**: Development Team
**Created**: 2025-08-28

## Overview

This feature implements a comprehensive multi-LLM provider architecture that enables seamless integration of multiple AI providers (Gemini, Ollama, OpenAI) while maintaining a unified API interface and ensuring response compatibility across all providers.

## Problem Statement

Currently, the system encounters Pydantic validation errors when processing responses from different LLM providers due to:

1. **Schema Mismatches**: Different providers return responses in varying formats
   - Ollama returns simple data types (e.g., `estimated_value: 3750000.0`)
   - Gemini expects complex nested objects (e.g., `EstimatedValue` with amount, currency, etc.)

2. **Template Incompatibility**: Single prompt template doesn't optimize for each provider's capabilities
   - Gemini can handle complex structured requests
   - Ollama performs better with simplified instructions

3. **Response Parsing Rigidity**: Current parsing assumes Gemini-style responses
   - No provider-specific adaptation
   - Hard validation failures instead of graceful transformation

## Business Requirements

### Primary Goals
- **BR-001**: Support multiple LLM providers simultaneously
- **BR-002**: Maintain unified API interface for all clients
- **BR-003**: Preserve existing Gemini functionality and performance
- **BR-004**: Enable cost-effective local processing via Ollama
- **BR-005**: Ensure response quality consistency across providers

### Secondary Goals
- **BR-006**: Extensible architecture for future LLM providers
- **BR-007**: Provider-specific performance optimization
- **BR-008**: Graceful degradation when providers are unavailable
- **BR-009**: Comprehensive monitoring and analytics per provider

## Technical Requirements

### Core Architecture
- **TR-001**: Provider-specific prompt template system
- **TR-002**: Response adapter/transformer layer
- **TR-003**: Unified response validation and error handling
- **TR-004**: Provider routing and fallback mechanisms
- **TR-005**: Configuration-driven provider selection

### Performance & Reliability
- **TR-006**: Response transformation with <100ms overhead
- **TR-007**: Provider health checks and circuit breakers
- **TR-008**: Caching layer compatible with all providers
- **TR-009**: Rate limiting per provider configuration

### Data & Validation
- **TR-010**: Schema-aware response transformation
- **TR-011**: Data integrity validation across providers
- **TR-012**: Confidence score normalization
- **TR-013**: Provider-specific metadata preservation

## Detailed Design

### 1. Provider-Specific Prompt Templates

#### Current Structure
```yaml
# prompts/templates/tender_extraction.yaml
inherits: base
task_description: |
  Extract comprehensive tender information...
schema_definition: |
  {
    "extracted_data": {
      "estimated_value": {
        "amount": "number",
        "currency": "string",
        "value_type": "enum"
      }
    }
  }
```

#### New Multi-Provider Structure
```
prompts/
├── templates/
│   ├── base/
│   │   ├── tender_extraction.yaml         # Base template
│   │   └── multi_document_extraction.yaml
│   ├── gemini/
│   │   ├── tender_extraction.yaml         # Gemini-optimized
│   │   └── multi_document_extraction.yaml
│   ├── ollama/
│   │   ├── tender_extraction.yaml         # Ollama-simplified
│   │   └── multi_document_extraction.yaml
│   └── openai/
│       ├── tender_extraction.yaml         # OpenAI-optimized
│       └── multi_document_extraction.yaml
```

#### Ollama Template Example
```yaml
# prompts/templates/ollama/tender_extraction.yaml
inherits: base

task_description: |
  Extract tender information in simple JSON format. Use exact field names as specified.

schema_definition: |
  {
    "project_title": "string",
    "estimated_value": "number - just the numeric amount",
    "currency": "string - currency code like EUR, USD",
    "submission_deadline": "string - ISO date format",
    "evaluation_criteria": [
      {
        "criterion": "string - name of criterion",
        "weight_percentage": "number - percentage from 0-100"
      }
    ]
  }

response_format: |
  Return ONLY valid JSON matching the exact schema above.
  Do not include markdown code blocks or explanations.
  Use simple data types - no nested objects for basic fields.
```

### 2. Response Adapter System

#### Adapter Interface
```python
class ResponseAdapter(ABC):
    """Abstract base for provider-specific response adapters."""

    @abstractmethod
    def adapt_response(self, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """Transform provider response to unified format."""
        pass

    @abstractmethod
    def get_supported_provider(self) -> str:
        """Return provider name this adapter supports."""
        pass
```

#### Ollama Response Adapter
```python
class OllamaResponseAdapter(ResponseAdapter):
    """Transforms Ollama responses to unified format."""

    def adapt_response(self, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Ollama simple format to TenderExtractedData format."""

        adapted = {}

        # Transform estimated_value from float to EstimatedValue object
        if "estimated_value" in raw_response and isinstance(raw_response["estimated_value"], (int, float)):
            adapted["estimated_value"] = {
                "amount": raw_response["estimated_value"],
                "currency": raw_response.get("currency", "EUR"),
                "value_type": "total",
                "vat_included": None
            }

        # Transform evaluation_criteria name->criterion field mapping
        if "evaluation_criteria" in raw_response:
            adapted["evaluation_criteria"] = []
            for criterion in raw_response["evaluation_criteria"]:
                if isinstance(criterion, dict) and "name" in criterion:
                    adapted_criterion = {
                        "criterion": criterion["name"],
                        "weight_percentage": criterion.get("weight", 0) * 100,  # Convert 0.45 to 45
                        "description": criterion.get("description")
                    }
                    adapted["evaluation_criteria"].append(adapted_criterion)

        # Copy other fields directly
        for field in ["project_title", "submission_deadline", "contracting_authority"]:
            if field in raw_response:
                adapted[field] = raw_response[field]

        return {"extracted_data": adapted}
```

#### Adapter Factory
```python
class ResponseAdapterFactory:
    """Factory for creating provider-specific response adapters."""

    _adapters = {
        "ollama": OllamaResponseAdapter,
        "gemini": GeminiResponseAdapter,  # Pass-through adapter
        "openai": OpenAIResponseAdapter,
    }

    @classmethod
    def get_adapter(cls, provider: str) -> ResponseAdapter:
        if provider not in cls._adapters:
            raise ValueError(f"No adapter available for provider: {provider}")
        return cls._adapters[provider]()
```

### 3. Enhanced Prompt Builder

#### Multi-Provider Prompt Selection
```python
class MultiProviderPromptBuilder(PromptBuilder):
    """Provider-aware prompt builder."""

    def build_prompt(
        self,
        document_content: str,
        config_name: str = "default",
        template_override: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Build prompt optimized for specific LLM provider."""

        # Determine provider from settings if not specified
        if provider is None:
            from app.config import settings
            provider = settings.llm_provider

        # Select provider-specific template path
        if provider != "gemini":  # Default templates are Gemini-optimized
            template_path = f"{provider}/{template_override or 'tender_extraction'}"
        else:
            template_path = template_override or 'tender_extraction'

        # Build prompt using provider-specific template
        return super().build_prompt(
            document_content=document_content,
            config_name=config_name,
            template_override=template_path,
            **kwargs
        )
```

### 4. Updated Extraction Service

#### Provider-Aware Processing
```python
class ExtractionService:
    """Enhanced extraction service with multi-provider support."""

    def __init__(self):
        self.llm_service = get_llm_service()
        self.provider_name = self.llm_service.get_provider_name()

        # Initialize provider-specific components
        self.response_adapter = ResponseAdapterFactory.get_adapter(self.provider_name)
        self.prompt_builder = MultiProviderPromptBuilder()

    def _parse_ai_response(self, ai_response: Dict[str, Any], document: DocumentContent) -> TenderExtractionResult:
        """Enhanced parsing with provider-specific adaptation."""

        try:
            # Step 1: Provider-specific response adaptation
            adapted_response = self.response_adapter.adapt_response(ai_response)

            # Step 2: Standard validation and parsing
            if "extracted_data" in adapted_response:
                extracted_data = TenderExtractedData(**adapted_response["extracted_data"])
                confidence_scores = ConfidenceScores(**(adapted_response.get("confidence_scores", {})))
                extraction_notes = ExtractionNotes(**(adapted_response.get("extraction_notes", {})))
            else:
                # Fallback for direct response format
                extracted_data = TenderExtractedData(**adapted_response)
                confidence_scores = ConfidenceScores()
                extraction_notes = ExtractionNotes()

            # Step 3: Add provider-specific metadata
            processing_metadata = ProcessingMetadata()
            processing_metadata.model = f"{self.provider_name}:{self.llm_service.model}"

            return TenderExtractionResult(
                extracted_data=extracted_data,
                confidence_scores=confidence_scores,
                extraction_notes=extraction_notes,
                processing_metadata=processing_metadata,
                raw_response=ai_response
            )

        except Exception as e:
            logger.error(f"Failed to parse {self.provider_name} response: {e}")

            # Enhanced error handling with provider context
            return TenderExtractionResult(
                extracted_data=TenderExtractedData(),
                confidence_scores=ConfidenceScores(),
                extraction_notes=ExtractionNotes(
                    ambiguities=[f"Failed to parse {self.provider_name} response: {str(e)}"]
                ),
                processing_metadata=ProcessingMetadata(
                    model=f"{self.provider_name}:{self.llm_service.model}",
                    extraction_complexity=ExtractionComplexity.COMPLEX
                ),
                raw_response=ai_response
            )
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] **P1-001**: Create new feature branch `feature/multi-llm-architecture`
- [ ] **P1-002**: Update Ollama mock server response format
- [ ] **P1-003**: Implement base ResponseAdapter interface
- [ ] **P1-004**: Create OllamaResponseAdapter with unit tests
- [ ] **P1-005**: Test basic Ollama response transformation

### Phase 2: Provider-Specific Templates (Week 1-2)
- [ ] **P2-001**: Restructure prompts directory for multi-provider support
- [ ] **P2-002**: Create Ollama-optimized tender extraction template
- [ ] **P2-003**: Create Ollama-optimized multi-document template
- [ ] **P2-004**: Implement MultiProviderPromptBuilder
- [ ] **P2-005**: Add provider detection and routing logic

### Phase 3: Integration & Testing (Week 2)
- [ ] **P3-001**: Update ExtractionService with provider-aware parsing
- [ ] **P3-002**: Implement comprehensive error handling
- [ ] **P3-003**: Add provider-specific metadata tracking
- [ ] **P3-004**: Create integration tests for all providers
- [ ] **P3-005**: Performance testing and optimization

### Phase 4: Quality & Documentation (Week 2-3)
- [ ] **P4-001**: Code review and quality assurance
- [ ] **P4-002**: Update API documentation
- [ ] **P4-003**: Create provider selection guide
- [ ] **P4-004**: Performance benchmarking report
- [ ] **P4-005**: Feature deployment and monitoring

## Testing Strategy

### Unit Testing Checklist
- [ ] **UT-001**: ResponseAdapter interface compliance tests
- [ ] **UT-002**: OllamaResponseAdapter transformation accuracy
- [ ] **UT-003**: GeminiResponseAdapter backward compatibility
- [ ] **UT-004**: MultiProviderPromptBuilder template selection
- [ ] **UT-005**: Provider-specific error handling scenarios
- [ ] **UT-006**: Schema validation edge cases
- [ ] **UT-007**: Data type transformation correctness
- [ ] **UT-008**: Configuration-driven provider routing

### Integration Testing Checklist
- [ ] **IT-001**: End-to-end Ollama document processing
- [ ] **IT-002**: End-to-end Gemini document processing (regression)
- [ ] **IT-003**: Multi-document batch processing all providers
- [ ] **IT-004**: Provider fallback and error recovery
- [ ] **IT-005**: Response format compatibility across providers
- [ ] **IT-006**: Performance comparison between providers
- [ ] **IT-007**: Mock server integration testing
- [ ] **IT-008**: Real API integration testing (limited)

### Quality Assurance Checklist

#### Code Quality
- [ ] **QA-001**: All code follows project style guidelines (black, isort, ruff)
- [ ] **QA-002**: Type hints on all new functions and methods
- [ ] **QA-003**: Comprehensive docstrings with examples
- [ ] **QA-004**: No hardcoded values - use configuration
- [ ] **QA-005**: Proper exception handling and logging
- [ ] **QA-006**: Security review - no exposed secrets or keys
- [ ] **QA-007**: Performance profiling - no significant regressions
- [ ] **QA-008**: Memory usage analysis for long-running processes

#### Testing Coverage
- [ ] **QA-009**: Minimum 90% test coverage for new code
- [ ] **QA-010**: All public methods have corresponding tests
- [ ] **QA-011**: Edge cases and error conditions covered
- [ ] **QA-012**: Provider-specific test scenarios
- [ ] **QA-013**: Backward compatibility tests pass
- [ ] **QA-014**: Performance benchmarks within acceptable ranges
- [ ] **QA-015**: Integration tests with real data samples
- [ ] **QA-016**: Load testing for concurrent provider usage

#### Code Review Checklist

#### Architecture & Design
- [ ] **CR-001**: Clear separation of concerns between providers
- [ ] **CR-002**: Extensible design for future LLM providers
- [ ] **CR-003**: Proper abstraction levels and interfaces
- [ ] **CR-004**: Configuration management follows best practices
- [ ] **CR-005**: Error handling is comprehensive and user-friendly
- [ ] **CR-006**: Logging provides adequate debugging information
- [ ] **CR-007**: Performance considerations addressed
- [ ] **CR-008**: Security implications reviewed

#### Implementation Quality
- [ ] **CR-009**: Code is readable and well-documented
- [ ] **CR-010**: Function/method names are descriptive and accurate
- [ ] **CR-011**: Complex logic is broken into smaller, testable units
- [ ] **CR-012**: No code duplication - DRY principle followed
- [ ] **CR-013**: Proper dependency injection and testability
- [ ] **CR-014**: Resource management (connections, files) handled correctly
- [ ] **CR-015**: Thread safety considerations addressed where needed
- [ ] **CR-016**: All TODOs and FIXMEs resolved or tracked

### Test Cases Documentation

#### Critical Test Scenarios

**TC-001: Ollama Simple Response Transformation**
```python
def test_ollama_simple_response_transformation():
    """Test basic Ollama response format transformation."""
    ollama_response = {
        "project_title": "Highway Project A1",
        "estimated_value": 2500000.0,
        "currency": "EUR",
        "evaluation_criteria": [
            {"name": "Technical Quality", "weight": 0.6},
            {"name": "Price", "weight": 0.4}
        ]
    }

    adapter = OllamaResponseAdapter()
    result = adapter.adapt_response(ollama_response)

    # Verify structure transformation
    assert "extracted_data" in result
    assert result["extracted_data"]["estimated_value"]["amount"] == 2500000.0
    assert result["extracted_data"]["evaluation_criteria"][0]["criterion"] == "Technical Quality"
    assert result["extracted_data"]["evaluation_criteria"][0]["weight_percentage"] == 60.0
```

**TC-002: Multi-Provider Template Selection**
```python
@pytest.mark.parametrize("provider,expected_template", [
    ("ollama", "ollama/tender_extraction"),
    ("gemini", "tender_extraction"),
    ("openai", "openai/tender_extraction")
])
def test_provider_template_selection(provider, expected_template):
    """Test correct template selection for each provider."""
    builder = MultiProviderPromptBuilder()

    with patch('app.config.settings.llm_provider', provider):
        result = builder.build_prompt(
            document_content="test content",
            provider=provider
        )

    assert expected_template in result['template_path']
```

**TC-003: Response Validation Across Providers**
```python
@pytest.mark.parametrize("provider_response,provider", [
    (OLLAMA_MOCK_RESPONSE, "ollama"),
    (GEMINI_MOCK_RESPONSE, "gemini"),
    (OPENAI_MOCK_RESPONSE, "openai")
])
def test_response_validation_all_providers(provider_response, provider):
    """Ensure all provider responses validate against TenderExtractionResult."""
    adapter = ResponseAdapterFactory.get_adapter(provider)
    adapted_response = adapter.adapt_response(provider_response)

    # Should not raise validation errors
    result = TenderExtractionResult(
        extracted_data=TenderExtractedData(**adapted_response["extracted_data"]),
        confidence_scores=ConfidenceScores(),
        extraction_notes=ExtractionNotes(),
        processing_metadata=ProcessingMetadata()
    )

    assert result.extracted_data.project_title is not None
```

## Risk Assessment

### Technical Risks
- **RISK-001**: Response format variations between LLM model versions
  - *Mitigation*: Version-specific adapters, comprehensive testing

- **RISK-002**: Performance overhead from response transformation
  - *Mitigation*: Benchmarking, caching, async processing

- **RISK-003**: Provider API availability and reliability
  - *Mitigation*: Circuit breakers, fallback mechanisms, monitoring

### Business Risks
- **RISK-004**: Inconsistent extraction quality between providers
  - *Mitigation*: Quality validation, confidence scoring, A/B testing

- **RISK-005**: Increased complexity in debugging and maintenance
  - *Mitigation*: Comprehensive logging, provider-specific metrics

## Success Metrics

### Technical KPIs
- Response transformation accuracy: >99%
- Provider compatibility: 100% (all configured providers work)
- Test coverage: >90% for all new code
- Performance overhead: <100ms per request
- Zero breaking changes to existing API

### Business KPIs
- Extraction accuracy consistency: <5% variance between providers
- Provider availability: >99.5% uptime
- Cost optimization: 20% reduction through Ollama usage
- Developer productivity: Seamless provider switching

## Monitoring & Observability

### Provider-Specific Metrics
- Request success/failure rates per provider
- Response transformation success rates
- Average processing time per provider
- Provider API health status
- Cost tracking per provider

### Alerts & Notifications
- Provider availability changes
- Response validation failures
- Performance degradation
- Unusual error rates

## Future Extensions

### Planned Enhancements
- **EXT-001**: Dynamic provider selection based on document complexity
- **EXT-002**: Provider performance-based automatic routing
- **EXT-003**: Custom response schemas per client
- **EXT-004**: Real-time provider cost optimization
- **EXT-005**: Multi-provider consensus validation

### Integration Opportunities
- **EXT-006**: Integration with additional LLM providers (Claude, Cohere)
- **EXT-007**: Provider-specific prompt optimization through A/B testing
- **EXT-008**: Machine learning-based provider selection
- **EXT-009**: Custom model fine-tuning integration

---

## Approval & Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Technical Lead | | | Pending |
| Product Owner | | | Pending |
| QA Lead | | | Pending |
| DevOps Lead | | | Pending |

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-08-28 | 1.0 | Initial feature specification | Development Team |

---

*This document will be updated throughout the implementation process to reflect changes, decisions, and lessons learned.*
