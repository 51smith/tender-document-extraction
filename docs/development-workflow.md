# Development Workflow Guide

This guide explains the development workflow for the Tender Document Extraction Service, including Docker setup, hot reload functionality, and best practices.

## Quick Start

```bash
# Start Ollama locally
ollama serve
ollama pull llama3:latest

# Start Docker development environment
make docker-dev

# Your environment is ready!
# - Application: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Health Check: http://localhost:8000/health
```

## Docker Development Environment

### Architecture Overview

The development environment consists of:
- **FastAPI Application** (with hot reload)
- **RQ Worker** (for background jobs)
- **Redis** (job queue and caching)
- **Local Ollama** (AI model server via host networking)

### Hot Reload System

Hot reload works through a combination of **Docker volume mounts** and **Uvicorn's file watching**:

#### 1. Volume Mounts (Docker Layer)
```yaml
volumes:
  # Mount source code for hot reload
  - ./app:/app/app:ro           # Your local app/ → container's /app/app
  - ./prompts:/app/prompts:ro   # Your local prompts/ → container's /app/prompts  
  - ./main.py:/app/main.py:ro   # Your local main.py → container's /app/main.py
```

- `:ro` = read-only mount (container can't modify your local files)
- Changes you make locally are **instantly reflected** inside the container
- No rebuilding or copying required

#### 2. Uvicorn File Watching (Application Layer)
```python
uvicorn.run(
    "main:app",
    host="0.0.0.0", 
    port=8000,
    reload=True,                    # Enable auto-reload
    reload_dirs=["app", "prompts"], # Watch these directories
    log_level="info"
)
```

#### 3. Hot Reload Flow

1. **You edit a file** (e.g., `app/services/gemini_service.py`)
2. **Volume mount reflects change** instantly in container at `/app/app/services/gemini_service.py`
3. **Uvicorn detects the change** through its file watcher
4. **Uvicorn restarts the application** automatically (takes ~1-2 seconds)
5. **Your changes are live** - no manual restart needed

#### 4. What Gets Watched

- ✅ `app/` directory (all Python modules, routers, services)
- ✅ `prompts/` directory (YAML templates, configs)  
- ✅ `main.py` (main application file)
- ❌ `requirements.txt` (would need container rebuild)
- ❌ `Dockerfile` (would need image rebuild)

#### 5. Development Experience

```bash
# Start environment once
make docker-dev

# Edit any file in app/ or prompts/
vim app/routers/extraction.py

# Save file → Uvicorn automatically restarts → Changes live in ~2 seconds
# No manual commands needed!
```

#### 6. Reload Logs

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [1] using WatchFiles  
INFO:     Started server process [8]
INFO:     Waiting for application startup.
INFO:     Application startup complete.

# After you edit a file:
INFO:     WatchFiles detected changes in 'app/services/gemini_service.py'. Reloading...
INFO:     Shutting down
INFO:     Finished server process [8]
INFO:     Started server process [9] 
INFO:     Application startup complete.
```

## Make Commands

### Docker Development Commands

```bash
# Start development environment
make docker-dev                # Complete setup and start
make docker-dev-up             # Start services only
make docker-dev-down           # Stop all services
make docker-dev-restart        # Restart services
make docker-dev-logs           # View real-time logs
```

### Local Development Commands

```bash
# Setup and dependencies
make setup-dev                 # Complete development setup
make install-dev               # Install development dependencies

# Code quality
make format                    # Format code (black + isort)
make lint                      # Lint code (ruff)
make type-check               # Type checking (mypy)
make security-check           # Security scan (bandit)
make quality-checks           # All quality checks

# Testing
make test                     # Run unit tests
make test-all                 # Comprehensive test suite
make test-api                 # API smoke tests
make test-coverage            # Coverage report

# Local server
make run-dev                  # Start local development server
make run-all                  # Start server + worker + Redis
```

## Network Configuration

### Ollama Connection

The Docker containers connect to your local Ollama server via:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"

environment:
  - OLLAMA_BASE_URL=http://host.docker.internal:11434
```

This allows containers to reach your local Ollama server at `localhost:11434`.

### Service Communication

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│      Redis      │    │   RQ Worker     │
│   Port: 8000    │    │   Port: 6379    │────│  (Background)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                              │
         └──────────────────┬───────────────────────────┘
                           │
                    ┌─────────────────┐
                    │  Local Ollama   │
                    │  Port: 11434    │
                    └─────────────────┘
```

## Environment Configuration

### Key Environment Variables

```bash
# AI Provider
LLM_PROVIDER=ollama                    # Use local Ollama
LLM_MODEL=llama3:latest               # Model to use
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Application
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your_super_secure_secret_key_for_development_environment_here_32_chars_minimum

# Redis (Docker service name)
REDIS_URL=redis://redis:6379/0
```

### File Locations

```
.env                    # Main environment file (mounted to containers)
.env.example           # Template with development defaults
docker-compose.dev.yml # Development Docker configuration
```

## Troubleshooting

### Common Issues

#### 1. Ollama Connection Failed
```bash
# Check if Ollama is running
curl http://localhost:11434/api/version

# Start Ollama if needed
ollama serve

# Check if model is available
ollama list
```

#### 2. Redis Connection Issues
```bash
# Check Redis container
docker-compose -f docker-compose.dev.yml logs redis

# Verify environment variable
echo $REDIS_URL  # Should be redis://redis:6379/0 for Docker
```

#### 3. Hot Reload Not Working
```bash
# Check file permissions
ls -la app/

# Verify volume mounts
docker-compose -f docker-compose.dev.yml exec app ls -la /app/app

# Check Uvicorn logs
make docker-dev-logs
```

#### 4. Port Already in Use
```bash
# Check what's using port 8000
lsof -i :8000

# Stop conflicting processes or use different port
docker-compose -f docker-compose.dev.yml down
```

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed

# Check all services
docker-compose -f docker-compose.dev.yml ps
```

## Best Practices

### Development Workflow

1. **Always start with Docker**: `make docker-dev`
2. **Use hot reload**: Edit files directly, let Uvicorn restart
3. **Test frequently**: `make test` after significant changes
4. **Check code quality**: `make quality-checks` before commits
5. **Monitor logs**: `make docker-dev-logs` for debugging

### Code Changes

1. **Python code**: Automatic hot reload (1-2 seconds)
2. **YAML prompts**: Automatic hot reload
3. **Dependencies**: Requires container rebuild
4. **Docker config**: Requires `make docker-dev-down && make docker-dev`

### Performance Tips

1. **Mount only what you need**: Current setup is optimized
2. **Use .dockerignore**: Exclude unnecessary files from build context
3. **Leverage caching**: Docker build stages are cached
4. **Monitor resources**: `docker stats` to check container usage

## Integration with IDEs

### VS Code

```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.formatting.provider": "black"
}
```

### PyCharm

1. Configure Python interpreter to use project venv
2. Set up Docker as remote interpreter (optional)
3. Configure test runner to use pytest

## Next Steps

Once your development environment is running:

1. **Explore the API**: Visit http://localhost:8000/docs
2. **Run tests**: `make test-all`  
3. **Check code quality**: `make quality-checks`
4. **Start developing**: Edit files in `app/` and see changes instantly
5. **Test with Ollama**: Upload documents via the API

The hot reload system ensures you get immediate feedback on your changes while maintaining the consistency and isolation of containerized development.