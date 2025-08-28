# Makefile for Tender Document Extraction Service

.PHONY: help install install-dev setup-dev clean test test-unit test-integration test-api test-all lint format type-check security-check pre-commit run-dev run-worker run-all build docker-build docker-run docker-dev docker-dev-up docker-dev-down docker-dev-logs docker-dev-restart quality-checks ci-checks

# Default target
help:
	@echo "Available targets:"
	@echo "  install       - Install production dependencies"
	@echo "  install-dev   - Install development dependencies"  
	@echo "  setup-dev     - Complete development setup"
	@echo "  clean         - Clean up generated files"
	@echo "  test          - Run all tests"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-integration - Run integration tests"
	@echo "  test-e2e      - Run end-to-end workflow tests"
	@echo "  test-failover - Run provider failover scenario tests"
	@echo "  test-batch    - Run large batch processing tests"
	@echo "  test-performance - Run performance and load tests"
	@echo "  test-containers - Run all containerized tests"
	@echo "  test-api      - Run API smoke tests (requires running server)"
	@echo "  test-all      - Run comprehensive test suite (units + quality + API)"
	@echo "  lint          - Run linting checks"
	@echo "  format        - Format code with black and isort"
	@echo "  type-check    - Run type checking with mypy"
	@echo "  security-check - Run security checks with bandit"
	@echo "  pre-commit    - Install and run pre-commit hooks"
	@echo "  run-dev       - Run development server"
	@echo "  run-worker    - Run RQ worker for job processing"
	@echo "  run-all       - Run both server and worker (recommended for dev)"
	@echo "  quality-checks - Run all code quality checks"
	@echo "  ci-checks     - Run all CI/CD checks"
	@echo "  build         - Build the application"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run application in Docker"
	@echo "  docker-dev    - Run development environment with Docker + Ollama"
	@echo "  docker-dev-up - Start Docker development environment with Ollama"
	@echo "  docker-dev-down - Stop Docker development environment"
	@echo "  docker-dev-logs - View Docker development logs"
	@echo "  docker-dev-restart - Restart Docker development services"
	@echo "  docker-test   - Run containerized test environment"
	@echo "  docker-test-up - Start test containers"
	@echo "  docker-test-down - Stop test containers"
	@echo "  install-redis - Install Redis via Homebrew"
	@echo "  start-redis   - Start Redis server"
	@echo "  stop-redis    - Stop Redis server"

# Installation targets
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

setup-dev: install-dev
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then \
		echo "Creating .env file from template..."; \
		cp .env.example .env; \
		echo "⚠️  Please edit .env file and configure your settings"; \
	fi
	pre-commit install
	@echo "✅ Development environment setup complete!"

# Cleanup
clean:
	@echo "Cleaning up generated files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	@echo "✅ Cleanup complete!"

# Testing targets
test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v -m integration

# Phase 5: Containerized Testing Targets
test-e2e:
	@echo "🔄 Running end-to-end workflow tests..."
	pytest tests/integration/test_e2e_workflows.py -v -m e2e

test-failover:
	@echo "🔀 Running provider failover scenario tests..."
	pytest tests/integration/test_provider_failover.py -v -m failover

test-batch:
	@echo "📦 Running large batch processing tests..."
	pytest tests/integration/test_large_batch_processing.py -v -m slow

test-performance:
	@echo "⚡ Running performance and load tests..."
	cd tests/performance && python performance_test_runner.py

test-containers:
	@echo "🐳 Running all containerized integration tests..."
	pytest tests/integration/ -v -m "integration or e2e or failover"

test-coverage:
	pytest --cov=app --cov-report=html --cov-report=term-missing

# Comprehensive testing (MANDATORY for Claude)
test-all:
	@echo "🧪 Running comprehensive test suite (MANDATORY)..."
	./test_all.sh

test-api:
	@echo "🔗 Running API smoke tests..."
	@echo "Creating test file..."
	@echo "Sample tender document for testing API endpoints" > /tmp/test_api_file.txt
	@echo "Testing health endpoint..."
	@curl -s -f "http://localhost:8000/health" > /dev/null || (echo "❌ Health endpoint failed - is server running?" && exit 1)
	@echo "✅ Health endpoint working"
	@echo "Testing batch extraction endpoint..."
	@curl -s -X POST "http://localhost:8000/api/v1/extract/batch" -H "Content-Type: multipart/form-data" -F "files=@/tmp/test_api_file.txt" -F "config_name=default" | grep -q "job_id" || (echo "❌ Batch extraction failed" && exit 1)
	@echo "✅ Batch extraction endpoint working"
	@echo "Testing jobs listing endpoint..."
	@curl -s -f "http://localhost:8000/api/v1/jobs" > /dev/null || (echo "❌ Jobs listing failed" && exit 1)
	@echo "✅ Jobs listing endpoint working"
	@echo "Testing statistics endpoint..."
	@curl -s -f "http://localhost:8000/api/v1/statistics" > /dev/null || (echo "❌ Statistics endpoint failed" && exit 1)
	@echo "✅ Statistics endpoint working"
	@rm -f /tmp/test_api_file.txt
	@echo "✅ All API smoke tests passed!"

# Code quality targets
format:
	@echo "Formatting code..."
	black app/ tests/ --line-length=100
	isort app/ tests/ --profile=black --line-length=100
	@echo "✅ Code formatting complete!"

lint:
	@echo "Running linting checks..."
	ruff check app/ tests/
	@echo "✅ Linting complete!"

type-check:
	@echo "Running type checks..."
	mypy app/
	@echo "✅ Type checking complete!"

security-check:
	@echo "Running security checks..."
	bandit -r app/ -f json
	@echo "✅ Security check complete!"

# Pre-commit
pre-commit:
	@echo "Installing and running pre-commit hooks..."
	pre-commit install
	pre-commit run --all-files
	@echo "✅ Pre-commit setup complete!"

# Combined quality checks
quality-checks: format lint type-check security-check
	@echo "✅ All code quality checks passed!"

ci-checks: lint type-check security-check test
	@echo "✅ All CI/CD checks passed!"

# Development server
run-dev:
	@echo "Starting development server..."
	python run_dev.py

# RQ Worker
run-worker:
	@echo "Starting RQ worker..."
	@if ! command -v redis-server >/dev/null 2>&1; then \
		echo "❌ Redis not found. Installing Redis..."; \
		$(MAKE) install-redis; \
	fi
	@if ! pgrep redis-server >/dev/null; then \
		echo "📡 Starting Redis server..."; \
		$(MAKE) start-redis; \
		sleep 2; \
	fi
	python run_worker.py

# Run both server and worker (recommended for development)
run-all:
	@echo "🚀 Starting full development environment..."
	@if ! command -v redis-server >/dev/null 2>&1; then \
		echo "❌ Redis not found. Installing Redis..."; \
		$(MAKE) install-redis; \
	fi
	@if ! pgrep redis-server >/dev/null; then \
		echo "📡 Starting Redis server..."; \
		$(MAKE) start-redis; \
		sleep 2; \
	fi
	@echo "Starting RQ worker in background..."
	python run_worker.py &
	@echo "Starting development server..."
	python run_dev.py

# Build targets
build:
	@echo "Building application..."
	python -m build
	@echo "✅ Build complete!"

# Docker targets
docker-build:
	@echo "Building Docker image..."
	docker build -t tender-extract:latest .
	@echo "✅ Docker image built!"

docker-run: docker-build
	@echo "Running Docker container..."
	docker run -p 8000:8000 --env-file .env tender-extract:latest

# Docker development environment with Ollama support
docker-dev-up:
	@echo "🐳 Starting Docker development environment with Ollama support..."
	@if [ ! -f .env ]; then \
		echo "📄 Creating .env file from template..."; \
		cp .env.example .env; \
		echo "✅ .env file created with development defaults"; \
		echo "💡 You can edit .env file to customize settings if needed"; \
	else \
		echo "✅ .env file exists"; \
	fi
	@echo "🔍 Checking if Ollama is running locally..."
	@if ! curl -s http://localhost:11434/api/version >/dev/null 2>&1; then \
		echo "❌ Ollama is not running on localhost:11434"; \
		echo "Please start Ollama with: ollama serve"; \
		echo "Or install Ollama from: https://ollama.com"; \
		exit 1; \
	fi
	@echo "✅ Ollama is running locally"
	@echo "🔍 Checking if llama3:latest is available..."
	@if ! ollama list | grep -q "llama3:latest"; then \
		echo "📥 Pulling llama3:latest model..."; \
		ollama pull llama3:latest; \
	fi
	@echo "✅ llama3:latest model is available"
	docker-compose -f docker-compose.dev.yml up -d
	@echo "⏳ Waiting for services to be healthy..."
	@sleep 15
	@echo "🔍 Checking service health..."
	@if curl -s http://localhost:8000/health >/dev/null 2>&1; then \
		echo "✅ Application is healthy and running at http://localhost:8000"; \
	else \
		echo "❌ Application health check failed"; \
		echo "Check logs with: make docker-dev-logs"; \
	fi
	@echo ""
	@echo "🎉 Docker development environment is ready!"
	@echo "📋 Available services:"
	@echo "   - Application: http://localhost:8000"
	@echo "   - API Docs: http://localhost:8000/docs"
	@echo "   - Redis: localhost:6379"
	@echo "   - Ollama: localhost:11434"

docker-dev-down:
	@echo "🛑 Stopping Docker development environment..."
	docker-compose -f docker-compose.dev.yml down
	@echo "✅ Docker development environment stopped!"

docker-dev-logs:
	@echo "📋 Viewing Docker development logs..."
	docker-compose -f docker-compose.dev.yml logs -f

docker-dev-restart:
	@echo "🔄 Restarting Docker development environment..."
	docker-compose -f docker-compose.dev.yml restart

docker-dev: docker-dev-up
	@echo "🚀 Docker development environment started!"
	@echo "Use 'make docker-dev-down' to stop when finished."

# Phase 5: Docker Test Environment
docker-test-up:
	@echo "🐳 Starting containerized test environment..."
	docker-compose -f docker-compose.test.yml up -d
	@echo "Waiting for services to be ready..."
	@sleep 30
	@echo "✅ Test environment ready!"

docker-test-down:
	@echo "🛑 Stopping containerized test environment..."
	docker-compose -f docker-compose.test.yml down
	@echo "✅ Test environment stopped!"

docker-test: docker-test-up
	@echo "🧪 Running integration tests in containerized environment..."
	pytest tests/integration/ -v -x --tb=short
	@$(MAKE) docker-test-down

# Database and Redis (for development)
install-redis:
	@echo "Installing Redis via Homebrew..."
	@if ! command -v brew >/dev/null 2>&1; then \
		echo "❌ Homebrew not found. Please install Homebrew first:"; \
		echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""; \
		exit 1; \
	fi
	brew install redis
	@echo "✅ Redis installed successfully!"

start-redis:
	@echo "Starting Redis server..."
	@if ! command -v redis-server >/dev/null 2>&1; then \
		echo "❌ Redis not found. Installing Redis..."; \
		$(MAKE) install-redis; \
	fi
	redis-server --daemonize yes --port 6379
	@echo "✅ Redis started on port 6379"

stop-redis:
	@echo "Stopping Redis server..."
	@if command -v redis-cli >/dev/null 2>&1; then \
		redis-cli shutdown; \
	else \
		echo "❌ redis-cli not found. Redis may not be installed."; \
	fi
	@echo "✅ Redis stopped"

# Dependency management
update-deps:
	@echo "Updating dependencies..."
	pip-compile requirements.in
	pip-compile requirements-dev.in
	@echo "✅ Dependencies updated!"

# API documentation
docs-serve:
	@echo "Starting API documentation server..."
	uvicorn main:app --reload --port 8001
	@echo "📚 API docs available at: http://localhost:8001/docs"

# Monitoring and health checks
health-check:
	@echo "Running health check..."
	curl -f http://localhost:8000/health || echo "❌ Health check failed"

detailed-health-check:
	@echo "Running detailed health check..."
	curl -f http://localhost:8000/health/detailed || echo "❌ Detailed health check failed"

# Performance testing
load-test:
	@echo "🔥 Running Locust load tests..."
	@echo "Make sure the test server is running at http://localhost:8001"
	cd tests/performance && locust -f locustfile.py -H http://localhost:8001 --headless -u 10 -r 2 -t 60s --html reports/load_test_report.html

load-test-ui:
	@echo "🎯 Starting Locust web interface..."
	@echo "Open http://localhost:8089 to control the load test"
	cd tests/performance && locust -f locustfile.py -H http://localhost:8001

# Database migrations (if needed in future)
migrate:
	@echo "Running database migrations..."
	# Add migration commands here
	@echo "⚠️  Database migrations not yet implemented"

# Backup and restore (if needed)
backup:
	@echo "Creating backup..."
	# Add backup commands here
	@echo "⚠️  Backup functionality not yet implemented"

restore:
	@echo "Restoring from backup..."
	# Add restore commands here
	@echo "⚠️  Restore functionality not yet implemented"

# Environment checks
check-env:
	@echo "Checking environment configuration..."
	@if [ ! -f .env ]; then \
		echo "❌ .env file not found. Run 'make setup-dev' first."; \
		exit 1; \
	fi
	@echo "✅ Environment configuration found"

# Full development workflow
dev-setup: setup-dev install-redis start-redis
	@echo "🚀 Complete development environment ready!"
	@echo "Run 'make run-dev' to start the development server"

# Production deployment preparation
prod-check: ci-checks check-env
	@echo "✅ Production deployment checks passed!"