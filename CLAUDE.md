This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

  Project Overview

  This is a FastAPI-based intelligent document extraction service that uses Google's Gemini 2.5 Pro model to extract structured information from tender documents and
   business proposals. The application combines traditional PDF processing with advanced AI analysis to provide accurate, contextual data extraction with confidence
  scoring.

  Core Architecture

  Main Components

  - FastAPI Application (app/main.py): Web framework with async endpoints for document processing
  - Google AI Integration (app/services/gemini_service.py): Gemini 2.5 Pro API client with rate limiting and error handling
  - Document Processing Pipeline: Multi-modal analysis supporting text, images, and structured data
  - Job Management System: Redis-backed job queue with real-time status tracking
  - Usage Analytics: Token consumption tracking and cost optimization

  Key Data Models

  - DocumentExtractionRequest: Configuration for AI-powered extraction operations
  - GeminiExtractionResult: AI analysis results with confidence scores and reasoning
  - BatchProcessingJob: Manages multiple document analysis with progress tracking
  - UsageMetrics: Token consumption and cost tracking for Gemini API calls

  Processing Workflow

  1. Document Upload: PDF validation → Multi-modal content extraction (text + images)
  2. AI Analysis: Structured prompts → Gemini 2.5 Pro analysis → JSON response parsing
  3. Quality Assessment: Confidence scoring → Human review flagging → Result validation
  4. Batch Processing: Concurrent document analysis → Progress tracking → Consolidated results

  Development Commands

  Setup

  # Create virtual environment
  python -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate

  # Install dependencies
  pip install -r requirements.txt

  # Install development dependencies (includes Google AI SDK)
  pip install -r requirements-dev.txt

  # Setup environment
  cp .env.example .env
  # Add your Google AI API key to .env file

  Running the Application

  # Run development server with hot reload
  python run_dev.py

  # Or run with uvicorn directly
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  # Run with production settings
  gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

  Testing

  # Run all tests (mocked Gemini API calls)
  pytest

  # Run with coverage reporting
  pytest --cov=app --cov-report=html

  # Run integration tests (requires API key and quota)
  pytest tests/integration/ --api-key

  # Run specific test categories
  pytest -m "not integration"  # Skip API-dependent tests
  pytest -m "gemini_api"       # Only Gemini API tests

  Code Quality

  # Format and organize code
  black app/ tests/ && isort app/ tests/

  # Lint code
  ruff check app/ tests/

  # Type checking
  mypy app/

  # Check for security issues
  bandit -r app/

  # Run all quality checks
  black app/ tests/ && isort app/ tests/ && ruff check app/ tests/ && mypy app/ && bandit -r app/

  Gemini API Management

  # Check current API usage
  python scripts/check_gemini_usage.py

  # Test API connectivity
  python scripts/test_gemini_connection.py

  # Generate usage report
  python scripts/generate_usage_report.py --days 7

  API Endpoints

  Document Processing

  - POST /api/v1/extract: Single document AI extraction
  - POST /api/v1/extract/batch: Multiple document processing with progress tracking
  - GET /api/v1/jobs/{job_id}: Job status and results retrieval
  - GET /api/v1/jobs/{job_id}/download: Export results in multiple formats

  System Management

  - GET /health: Basic health check including Gemini API connectivity
  - GET /api/v1/usage: Current API usage and remaining quota
  - GET /api/v1/models: Available Gemini model information and capabilities

  Gemini 2.5 Pro Integration

  Model Capabilities

  - Multi-modal Analysis: Processes text, images, tables, and charts from documents
  - Advanced Reasoning: Contextual understanding of tender requirements and business logic
  - Structured Output: Reliable JSON generation with schema validation
  - Large Context Window: Handles complete tender documents (up to 2M tokens)

  Prompt Engineering Strategy

  # Example structured prompt for tender analysis
  TENDER_EXTRACTION_PROMPT = """
  You are an expert at analyzing tender documents. Extract the following information in JSON format:

  REQUIRED FIELDS:
  - project_title: Clear, concise project name
  - estimated_value: Numeric value in EUR (null if not specified)
  - submission_deadline: ISO 8601 datetime
  - contracting_authority: Organization name and contact details
  - evaluation_criteria: Array of criterion objects with weights

  ANALYSIS REQUIREMENTS:
  1. Read the entire document for context
  2. Cross-reference information across sections
  3. Identify implicit requirements and constraints
  4. Flag any ambiguities or missing critical information

  CONFIDENCE SCORING:
  - Include confidence (0-1) for each extracted field
  - Explain reasoning for low confidence scores
  - Suggest improvements for unclear sections

  Document content: {document_content}

  Return valid JSON matching this schema: {json_schema}
  """

  Rate Limiting & Cost Optimization

  - Smart Caching: Document hash-based result caching to avoid duplicate API calls
  - Progressive Analysis: Use cheaper models for initial classification, Gemini 2.5 Pro for complex extraction
  - Batch Processing: Optimize token usage through intelligent document chunking
  - Usage Monitoring: Real-time tracking of tokens, requests, and costs

  Error Handling Strategy

  # Gemini API error handling patterns
  RETRY_STRATEGIES = {
      'RATE_LIMIT_EXCEEDED': ExponentialBackoff(max_retries=5),
      'QUOTA_EXCEEDED': CircuitBreaker(failure_threshold=3),
      'SAFETY_FILTER': AlternativePromptStrategy(),
      'MALFORMED_RESPONSE': ResponseValidationRecovery(),
  }

  Project Structure

  tenderextract/
  ├── app/
  │   ├── main.py                     # FastAPI application entry
  │   ├── config.py                   # Settings with Gemini API configuration
  │   ├── core/
  │   │   ├── exceptions.py           # Custom exceptions for AI processing
  │   │   ├── security.py            # API key management and rotation
  │   │   └── rate_limiter.py        # Gemini API rate limiting logic
  │   ├── models/
  │   │   ├── extraction.py          # Pydantic models for AI responses
  │   │   ├── gemini.py              # Gemini API request/response models
  │   │   └── jobs.py               # Job management data models
  │   ├── routers/
  │   │   ├── extraction.py          # Document processing endpoints
  │   │   ├── jobs.py               # Job management endpoints
  │   │   └── usage.py              # API usage and monitoring endpoints
  │   ├── services/
  │   │   ├── gemini_service.py      # Google AI API client and prompt management
  │   │   ├── document_processor.py  # PDF to multi-modal content conversion
  │   │   ├── job_manager.py         # Background job processing with Redis
  │   │   ├── cache_service.py       # Result caching and invalidation
  │   │   └── usage_tracker.py      # API usage analytics and cost tracking
  │   └── utils/
  │       ├── prompt_templates.py    # Structured prompts for different document types
  │       ├── response_parser.py     # JSON parsing and validation from AI responses
  │       └── document_utils.py      # PDF processing and image extraction
  ├── tests/
  │   ├── unit/
  │   │   ├── test_gemini_service.py # Mocked Gemini API tests
  │   │   └── test_document_processing.py
  │   ├── integration/
  │   │   ├── test_gemini_api.py     # Real API integration tests (quota-limited)
  │   │   └── test_end_to_end.py     # Full workflow tests
  │   └── fixtures/
  │       ├── sample_documents/       # Test PDFs and expected outputs
  │       └── mock_responses/         # Recorded Gemini API responses
  ├── scripts/
  │   ├── check_gemini_usage.py      # API usage monitoring
  │   ├── migrate_prompts.py         # Prompt template migration utilities
  │   └── batch_process_samples.py   # Bulk document processing for testing
  ├── requirements.txt               # Core dependencies including google-generativeai
  ├── requirements-dev.txt           # Development tools and testing frameworks
  ├── docker-compose.yml             # Local development with Redis
  └── .env.example                   # Template with Gemini API configuration

  Configuration

  Environment Variables

  # Google AI Configuration
  GOOGLE_API_KEY=your_gemini_api_key_here
  GEMINI_MODEL=gemini-2.5-pro
  GEMINI_TEMPERATURE=0.1
  GEMINI_MAX_TOKENS=8192
  GEMINI_RATE_LIMIT_RPM=300
  GEMINI_RATE_LIMIT_TPM=50000

  # Application Settings
  REDIS_URL=redis://localhost:6379/0
  MAX_FILE_SIZE=50000000  # 50MB for large tender documents
  RESULT_CACHE_TTL=86400  # 24 hours

  # Monitoring & Analytics
  ENABLE_USAGE_TRACKING=true
  COST_ALERT_THRESHOLD=100.00  # USD
  LOG_LEVEL=INFO

  Gemini 2.5 Pro Specific Settings

  # Recommended configuration for document extraction
  GEMINI_CONFIG = {
      "model": "gemini-2.5-pro",
      "generation_config": {
          "temperature": 0.1,        # Low temperature for structured extraction
          "top_p": 0.9,
          "top_k": 40,
          "max_output_tokens": 8192,
          "response_mime_type": "application/json"
      },
      "safety_settings": [
          {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
          {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
          {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
          {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
      ]
  }

  Development Best Practices

  Google AI Integration

  - API Key Security: Use Google Cloud Secret Manager in production, never commit keys
  - Quota Management: Implement usage tracking and automatic scaling based on demand
  - Response Validation: Always validate JSON responses and handle malformed outputs gracefully
  - Context Optimization: Use document chunking strategies to maximize context window utilization
  - Model Selection: Use Gemini 2.5 Pro for complex reasoning, consider Flash for simple extractions

  Async Processing Patterns

  # Example async Gemini API call with proper error handling
  async def extract_document_data(document: bytes) -> ExtractionResult:
      try:
          async with AsyncGeminiClient() as client:
              response = await client.generate_content_async(
                  prompt=build_extraction_prompt(document),
                  generation_config=GEMINI_CONFIG
              )
              return parse_and_validate_response(response)
      except GeminiRateLimitError:
          await asyncio.sleep(calculate_backoff_delay())
          return await extract_document_data(document)  # Retry
      except GeminiQuotaExceededError:
          raise ServiceUnavailableError("AI processing temporarily unavailable")

  Cost Optimization Strategies

  1. Intelligent Caching: Cache results by document content hash
  2. Progressive Analysis: Use document classification to choose appropriate model
  3. Batch Processing: Group similar documents to reduce API overhead
  4. Content Optimization: Remove redundant text and focus on key sections
  5. Usage Monitoring: Daily cost tracking with automatic alerts

  Testing with External APIs

  # Mock Gemini responses for unit tests
  @pytest.fixture
  def mock_gemini_response():
      return {
          "project_title": "Highway Construction Project A1",
          "estimated_value": 5000000.0,
          "confidence_scores": {"project_title": 0.95, "estimated_value": 0.88},
          "processing_metadata": {"tokens_used": 1247, "processing_time": 2.3}
      }

  # Integration tests with real API (limited usage)
  @pytest.mark.integration
  @pytest.mark.skipif(not os.getenv("GOOGLE_API_KEY"), reason="API key required")
  async def test_real_gemini_extraction():
      # Test with minimal API usage
      pass

  Security & Privacy

  - Data Residency: Consider document sensitivity and Google's data handling policies
  - Audit Logging: Log all AI processing requests with user consent tracking
  - Content Filtering: Sanitize sensitive information before API calls
  - Access Control: Implement role-based access to AI processing features

  Monitoring & Observability

  Key Metrics

  - API Usage: Requests per minute, tokens consumed, costs incurred
  - Performance: Response times, extraction accuracy, confidence scores
  - Reliability: Error rates, retry frequencies, circuit breaker activations
  - Business: Documents processed, extraction success rates, user satisfaction

  Alerting Thresholds

  - Daily cost exceeds $50 USD
  - Error rate above 5% for 5 minutes
  - Average confidence score below 0.8 for 1 hour
  - API quota utilization above 80%

  Deployment Considerations

  Production Readiness

  - Horizontal Scaling: Multiple worker instances with Redis coordination
  - Load Balancing: Distribute API calls across multiple Google AI endpoints
  - Disaster Recovery: Fallback to alternative AI providers or manual processing
  - Performance Monitoring: APM integration with Gemini API metrics

  Docker Configuration

  FROM python:3.11-slim
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY app/ app/
  ENV GOOGLE_API_KEY=${GOOGLE_API_KEY}
  CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker"]

# Project Context
- PRD: See `./docs/PRD.md` for complete product requirements
- Implementation should follow the specifications in the PRD
- I want to build this project in stages. For now only follow the prompt. I'll give you the next step after reviewing this one.
- 

# 🚨 MANDATORY TESTING REQUIREMENTS

## ⚠️ CRITICAL: Testing is Non-Negotiable

**BEFORE making ANY changes to code, Claude MUST:**

1. **Always run unit tests first:**
   ```bash
   pytest
   ```

2. **After ANY code changes, Claude MUST:**
   - Run unit tests again: `pytest`
   - Run code quality checks: `black app/ tests/ && isort app/ tests/ && ruff check app/ tests/ && mypy app/`
   - Start the development server and test ALL affected API endpoints

3. **For API changes, Claude MUST perform smoke tests:**
   ```bash
   # Test all main endpoints
   curl -X GET "http://localhost:8000/health"
   curl -X POST "http://localhost:8000/api/v1/extract/batch" -H "Content-Type: multipart/form-data" -F "files=@test_file.txt"
   curl -X GET "http://localhost:8000/api/v1/jobs"
   curl -X GET "http://localhost:8000/api/v1/statistics"
   ```

4. **Test coverage requirements:**
   - All unit tests must pass (0 failures)
   - All API endpoints must respond correctly
   - Any removed endpoints must return 404
   - Any new functionality must have corresponding tests

**FAILURE TO TEST = INCOMPLETE TASK**

If Claude skips testing, the user should remind Claude that testing is mandatory per the project guidelines.

---

# ✅ Development Guidelines & Best Practices

## 🧪 Testing
- [ ] Test-driven development (**TDD**) approach.  
- [ ] Use **pytest** as the main testing framework.  
- [ ] Use **pytest-asyncio** for async code.  
- [ ] Use **pytest-mock** or `unittest.mock` for mocking.  
- [ ] Use **pytest-cov** for coverage reporting.  
- [ ] Use pytest fixtures for test data and setup.  
- [ ] Use **responses** or **httpx-mock** for mocking HTTP requests.  
- [ ] Write unit tests with mocking for external API calls.  
- [ ] Write integration tests that cover the full workflow.  
- [ ] Write functional tests for end-to-end scenarios simulating real users.  
- [ ] Include test cases for **edge cases** and **error handling**.  
- [ ] Use a separate configuration for tests.  
- [ ] Use a test database or in-memory database for tests.  
- [ ] Use logging in tests to capture important events and errors.  
- [ ] Measure test coverage with **coverage.py**.  

---

## 🛠️ Code Quality & Security
- [ ] Follow best practices for **code structure** and organization.  
- [ ] Use **type hints** everywhere.  
- [ ] Use **black** and **isort** for formatting.  
- [ ] Use **ruff** for linting.  
- [ ] Use **mypy** for type checking.  
- [ ] Use **bandit** for security checks.  

---

## ⚙️ CI/CD
- [ ] Use **GitHub Actions** for CI/CD.  
- [ ] Run tests, linting, type checking, and security checks in CI.  
- [ ] Track test coverage in CI pipelines.  

---

## 📖 Documentation & API Design
- [ ] Write clear, concise documentation for code and APIs.  
- [ ] Include **request and response examples** in docs.  
- [ ] Follow **RESTful API design principles**.  
- [ ] Use **OpenAPI/Swagger** for API documentation.  
- [ ] Use **Pydantic models** for request/response schemas.  

---

## 🏗️ Frameworks & Libraries
- [ ] Use **FastAPI** for the web framework.  
- [ ] Use **Pydantic** for data validation and settings management.  
- [ ] Use **Redis** for job queue and caching.  
- [ ] Use **asyncio** for async/concurrent processing.  
- [ ] Use **HTTPX** or **AIOHTTP** for async HTTP requests.  
- [ ] Use **Docker** for containerization.  
- [ ] Use **Git** for version control.  

---

## 🤖 API Integration (Gemini 2.5 Pro)
- [ ] Use the **`google-generativeai`** package.  
- [ ] Follow **Google AI best practices** for interacting with Gemini.  
- [ ] Use structured prompts for document extraction.  
- [ ] Always test with real API & API key (limit usage to avoid costs).  
- [ ] Implement **rate limiting** and **retries** for API calls.  
- [ ] Implement **caching** to avoid duplicate API calls.  
- [ ] Implement **usage tracking** and cost optimization.  
- [ ] Use **async/await** for API calls.  
- [ ] Implement proper error handling for API errors/exceptions.  

---

## ⚠️ Error Handling & Logging
- [ ] Implement proper error handling with correct HTTP status codes.  
- [ ] Use dependency injection for services and components.  
- [ ] Use **logging** for observability and debugging.  

---

## 🔐 Configuration & Security
- [ ] Use environment variables for configuration (API keys, sensitive info).  
- [ ] Follow best practices for **security** and **privacy**, especially when handling documents and API keys.  

---

## 📦 Background Processing
- [ ] Use FastAPI background tasks or **Celery** if needed.  

---

## 🚀 Production Readiness
- [ ] Ensure code is **production ready**: error handling, logging, configuration management, observability, and security.  

---

## 🔀 Git Workflow Best Practices
- [ ] **You must Always Use feature branches** for new work! (e.g., `feature/add-auth`).  
- [ ] Keep **main branch stable** — always production-ready.  
- [ ] Use **pull requests (PRs)** for merging into main.  
- [ ] Require **code reviews** before merging.  
- [ ] Use **conventional commits** (e.g., `feat:`, `fix:`, `docs:`).  
- [ ] Rebase (or squash) before merging to keep history clean.  
- [ ] Use **protected branches** (require CI to pass before merging).  
- [ ] Tag releases with **semantic versioning** (`v1.2.0`).  
- [ ] Automate changelogs and releases with GitHub Actions.  
- [ ] Delete merged branches to keep repo clean.  

## Core Prompt Engineering Principles

  "When working with API prompts, prioritize maintainability and systematic organization:"

  1. Centralized Prompt Management
    - Store all prompts in dedicated configuration files (YAML/JSON)
    - Use template inheritance for common prompt patterns
    - Version control prompt changes with clear commit messages
    - Never hardcode prompts directly in business logic
  2. Modular Prompt Architecture
    - Break complex prompts into reusable components (system, context, task, constraints)
    - Create prompt builders that compose components dynamically
    - Use consistent naming conventions for prompt variables and templates
    - Implement prompt validation before API calls
  3. Testing and Iteration Framework
    - Create comprehensive test suites for each prompt variant
    - Implement A/B testing capabilities for prompt optimization
    - Log prompt performance metrics (accuracy, token usage, response time)
    - Use deterministic examples for regression testing
  4. Documentation Standards
    - Document prompt purpose, expected inputs/outputs, and performance characteristics
    - Include example interactions and edge cases
    - Track prompt evolution with version history and rationale
    - Create prompt style guides for team consistency
  5. Performance Monitoring
    - Implement token usage tracking per prompt type
    - Monitor response quality metrics and user feedback
    - Set up alerts for prompt performance degradation
    - Create dashboards for prompt analytics

## Example instruction format:
 - "Always structure prompts using the YAML template system in `prompts/templates/`.
 - Use the PromptBuilder class to compose prompts programmatically.
 - Test every prompt change against the golden dataset in `tests/prompt_validation/`.
 - Document prompt changes in `PROMPT_CHANGELOG.md` with performance impact."
 - This approach ensures prompts remain maintainable, testable, and optimizable as the project scales.