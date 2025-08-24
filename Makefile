# Makefile for Tender Document Extraction Service

.PHONY: help install install-dev setup-dev clean test test-unit test-integration lint format type-check security-check pre-commit run-dev build docker-build docker-run quality-checks ci-checks

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
	@echo "  lint          - Run linting checks"
	@echo "  format        - Format code with black and isort"
	@echo "  type-check    - Run type checking with mypy"
	@echo "  security-check - Run security checks with bandit"
	@echo "  pre-commit    - Install and run pre-commit hooks"
	@echo "  run-dev       - Run development server"
	@echo "  quality-checks - Run all code quality checks"
	@echo "  ci-checks     - Run all CI/CD checks"
	@echo "  build         - Build the application"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run application in Docker"

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

test-coverage:
	pytest --cov=app --cov-report=html --cov-report=term-missing

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

# Database and Redis (for development)
start-redis:
	@echo "Starting Redis server..."
	redis-server --daemonize yes --port 6379
	@echo "✅ Redis started on port 6379"

stop-redis:
	@echo "Stopping Redis server..."
	redis-cli shutdown
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
	@echo "Running load tests..."
	# Add load testing commands here (e.g., locust, wrk, etc.)
	@echo "⚠️  Load testing not yet implemented"

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
dev-setup: setup-dev start-redis
	@echo "🚀 Complete development environment ready!"
	@echo "Run 'make run-dev' to start the development server"

# Production deployment preparation
prod-check: ci-checks check-env
	@echo "✅ Production deployment checks passed!"