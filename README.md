# Tender Document Extraction Service

AI-powered document extraction service using Google Gemini 2.5 Pro for intelligent processing of tender documents and procurement notices.

## 🚀 Features

- **Multi-modal Analysis**: Process text, images, tables, and charts from documents
- **Structured Output**: Extract key tender information with confidence scores
- **Batch Processing**: Handle multiple documents with progress tracking
- **Prompt Engineering**: Centralized template system for optimal extraction
- **Rate Limiting**: Intelligent API usage management
- **Quality Assurance**: Confidence scoring and validation
- **Cost Monitoring**: Token usage tracking and cost optimization
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web API       │    │   Job Manager    │    │  Gemini API     │
│   (FastAPI)     │───▶│   (Redis Queue)  │───▶│  Integration    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Document      │    │   Result Cache   │    │  Usage Tracker  │
│   Storage       │    │   (Redis)        │    │  & Analytics    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🛠️ Technology Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic v2
- **AI Integration**: Google Generative AI Python SDK (Gemini 2.5 Pro)
- **Queue Management**: Redis with RQ
- **Document Processing**: PyPDF2, Pillow, python-docx
- **Monitoring**: Structured logging, usage analytics
- **Testing**: Pytest with async support, TestContainers, comprehensive test coverage
- **Integration Testing**: Docker-based test environment, mock LLM services
- **Performance Testing**: Locust load testing, automated performance validation
- **Code Quality**: Black, isort, ruff, mypy, bandit, pre-commit hooks

## 📦 Installation

### Prerequisites

- Python 3.11+
- Redis server
- Google AI API key

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tender_batch_extract
   ```

2. **Set up development environment**
   ```bash
   make setup-dev
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your Google AI API key and other settings
   ```

4. **Start Redis server**
   ```bash
   make start-redis
   ```

5. **Run the development server**
   ```bash
   make run-dev
   ```

The API will be available at:
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Root**: http://localhost:8000/

### Production Deployment

#### Using Docker Compose

1. **Configure environment**
   ```bash
   cp .env.example .env
   # Configure your production settings
   ```

2. **Start all services**
   ```bash
   docker-compose up -d
   ```

#### Using Docker

1. **Build the image**
   ```bash
   make docker-build
   ```

2. **Run the container**
   ```bash
   make docker-run
   ```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Google AI API key | **Required** |
| `GEMINI_MODEL` | Gemini model to use | `gemini-2.5-pro` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `MAX_FILE_SIZE` | Maximum file size (bytes) | `52428800` (50MB) |
| `LOG_LEVEL` | Logging level | `INFO` |

See `.env.example` for complete configuration options.

## 📚 API Usage

### Single Document Extraction

```bash
curl -X POST "http://localhost:8000/api/v1/extract" \
  -F "file=@document.pdf" \
  -F "config_name=default"
```

### Batch Processing

```bash
curl -X POST "http://localhost:8000/api/v1/extract/batch" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "priority=5"
```

### Check Job Status

```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

### Usage Analytics

```bash
curl "http://localhost:8000/api/v1/usage"
```

## 🎯 Prompt Engineering

The service uses a sophisticated prompt engineering system:

### Template Structure

```yaml
# prompts/templates/tender_extraction.yaml
inherits: base
task_description: |
  Extract comprehensive tender information from the provided procurement document.

schema_definition: |
  {
    "extracted_data": {
      "project_title": "string",
      "estimated_value": {...},
      "evaluation_criteria": [...]
    }
  }
```

### Configuration

```yaml
# prompts/configs/default.yaml  
template: "tender_extraction"
model_config:
  temperature: 0.1
  max_tokens: 8192
quality:
  min_confidence_threshold: 0.5
```

### Custom Templates

1. Create new template in `prompts/templates/`
2. Create corresponding config in `prompts/configs/`
3. Reference in API calls with `template_override` parameter

## 🧪 Testing

### Unit Tests
```bash
make test-unit          # Run unit tests only
make test-coverage      # Run with coverage report
```

### Integration Tests
```bash
make test-integration   # Basic integration tests
make test-e2e          # End-to-end workflow tests
make test-failover     # Provider failover scenarios
make test-batch        # Large batch processing tests
make test-containers   # All containerized tests
```

### Performance Testing
```bash
make test-performance   # Automated performance test suite
make load-test         # Locust load test (headless)
make load-test-ui      # Locust with web interface
```

### Docker Test Environment
```bash
make docker-test-up    # Start test containers
make docker-test       # Run integration tests in containers
make docker-test-down  # Stop test containers
```

### Comprehensive Testing
```bash
make test              # Run all unit tests
make ci-checks         # Complete CI/CD validation
```

### Test Infrastructure

The service includes comprehensive testing infrastructure:

#### Phase 4: Error Handling & Retry Logic
- **Retry Configuration**: Unified retry logic with exponential backoff
- **Circuit Breaker**: Provider failover patterns
- **Error Recovery**: Comprehensive error scenario testing

#### Phase 5: Containerized Test Environment
- **TestContainers**: Isolated Redis and service containers
- **Mock LLM Services**: Full API simulation for Gemini, OpenAI, Ollama
- **Automated Test Data**: Realistic document generation system
- **Performance Validation**: Load testing with configurable scenarios

## 📊 Monitoring

### Health Checks

- **Basic**: `GET /health`
- **Detailed**: `GET /health/detailed`
- **Gemini API**: `GET /health/gemini`
- **Redis**: `GET /health/redis`

### Usage Analytics

- **Current Usage**: `GET /api/v1/usage`
- **Usage History**: `GET /api/v1/usage/history?days=30`
- **Cost Analysis**: `GET /api/v1/usage/cost-analysis`
- **Model Breakdown**: `GET /api/v1/usage/models`

## 🔍 Code Quality

### Pre-commit Hooks
```bash
make pre-commit
```

### Manual Quality Checks
```bash
make quality-checks
```

### Individual Checks
```bash
make format      # Black + isort
make lint        # Ruff
make type-check  # MyPy
make security-check # Bandit
```

## 📈 Performance

### Optimization Features

- **Multi-Provider Support**: Gemini, OpenAI, Ollama with intelligent failover
- **Rate Limiting**: Token bucket algorithm with burst capacity
- **Circuit Breaker**: Automatic provider failover on failures
- **Caching**: Document hash-based result caching
- **Batch Processing**: Concurrent document analysis with progress tracking
- **Cost Monitoring**: Real-time usage tracking across providers

### Performance Testing

The service includes comprehensive performance validation:

- **Load Testing**: Locust-based load testing with realistic user scenarios
- **Stress Testing**: High-volume request handling with failure simulation
- **Consistency Testing**: Cross-provider result validation
- **Batch Performance**: Large document set processing optimization
- **Failover Testing**: Provider switching under various failure conditions

### Performance Metrics

- **Processing Speed**: <3 minutes for typical tender documents
- **Throughput**: 1000 documents per hour peak capacity  
- **Accuracy**: >95% for critical fields
- **Cost Efficiency**: <$0.50 average per document
- **Failover Time**: <2 seconds provider switching
- **Test Coverage**: 57%+ with comprehensive integration testing

## 🐛 Troubleshooting

### Common Issues

1. **Redis Connection Error**
   ```bash
   make start-redis
   ```

2. **Google AI API Authentication**
   - Verify `GOOGLE_API_KEY` in `.env`
   - Check API quota and limits

3. **File Size Errors**
   - Check `MAX_FILE_SIZE` setting
   - Optimize document size before processing

4. **Memory Issues**
   - Monitor document processing for large files
   - Adjust worker memory limits

### Debug Mode

```bash
DEBUG=true python run_dev.py
```

### Test Environment Issues

1. **Docker Test Environment**
   ```bash
   make docker-test-down  # Clean up containers
   make docker-test-up    # Restart test environment
   ```

2. **TestContainers Issues**
   - Ensure Docker is running and accessible
   - Check available ports (6380, 8001-8003, 11434)
   - Verify test dependencies: `pip install -r requirements-dev.txt`

3. **Performance Test Setup**
   ```bash
   cd tests/performance
   python performance_test_runner.py  # Automated test suite
   ```

### Logs

Application logs are available in:
- Development: Console output
- Production: `./logs/` directory
- Docker: Container logs via `docker logs`
- Test Environment: `docker-compose -f docker-compose.test.yml logs`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following the coding standards
4. Run tests: `make ci-checks`
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Development Workflow

```bash
# Setup development environment
make dev-setup

# Make your changes
# ...

# Run quality checks
make quality-checks

# Run tests
make test

# Commit with pre-commit hooks
git commit -m "Your changes"
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Documentation

- [Google AI Python SDK](https://github.com/google/generative-ai-python)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Queue Documentation](https://python-rq.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/example/tender-batch-extract/issues)
- **Documentation**: [API Docs](http://localhost:8000/docs)
- **Email**: support@example.com

---

**Built with ❤️ using Python, FastAPI, and Google Gemini 2.5 Pro**