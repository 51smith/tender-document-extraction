"""Integration test configuration with TestContainers."""

import asyncio


import httpx
import pytest
import redis
from testcontainers.compose import DockerCompose
from testcontainers.redis import RedisContainer

from app.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    """Start Redis container for integration tests."""
    with RedisContainer("redis:7-alpine") as redis_container:
        yield redis_container


@pytest.fixture(scope="session")
def redis_client(redis_container: RedisContainer) -> Generator[redis.Redis, None, None]:
    """Create Redis client connected to test container."""
    client = redis.Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        db=1,  # Use separate DB for tests
        decode_responses=True,
    )

    # Wait for Redis to be ready
    for _ in range(30):
        try:
            client.ping()
            break
        except redis.ConnectionError:
            time.sleep(0.1)
    else:
        raise Exception("Redis container did not become ready in time")

    yield client

    # Cleanup
    client.flushdb()
    client.close()


@pytest.fixture(scope="session")
def test_compose_stack() -> Generator[DockerCompose, None, None]:
    """Start full test stack with Docker Compose."""
    compose_path = Path(__file__).parent.parent.parent / "docker-compose.test.yml"

    with DockerCompose(
        filepath=str(compose_path.parent), compose_file_name="docker-compose.test.yml"
    ) as compose:
        # Wait for all services to be healthy
        _wait_for_services_ready(compose)
        yield compose


def _wait_for_services_ready(compose: DockerCompose, timeout: int = 120) -> None:
    """Wait for all services to be ready."""
    services_to_check = {
        "redis-test": {"host": "localhost", "port": 6380, "check": "redis"},
        "app-test": {"host": "localhost", "port": 8001, "check": "http", "path": "/health"},
        "mock-gemini": {"host": "localhost", "port": 8002, "check": "http", "path": "/health"},
        "mock-openai": {"host": "localhost", "port": 8003, "check": "http", "path": "/health"},
        "mock-ollama": {"host": "localhost", "port": 11434, "check": "http", "path": "/health"},
    }

    start_time = time.time()
    ready_services = set()

    while len(ready_services) < len(services_to_check) and (time.time() - start_time) < timeout:
        for service_name, config in services_to_check.items():
            if service_name in ready_services:
                continue

            try:
                if config["check"] == "redis":
                    client = redis.Redis(host=config["host"], port=config["port"], socket_timeout=1)
                    client.ping()
                elif config["check"] == "http":
                    response = httpx.get(
                        f"http://{config['host']}:{config['port']}{config['path']}", timeout=5
                    )
                    if response.status_code == 200:
                        ready_services.add(service_name)
            except Exception:
                pass

        if len(ready_services) < len(services_to_check):
            time.sleep(2)

    if len(ready_services) < len(services_to_check):
        missing = set(services_to_check.keys()) - ready_services
        raise Exception(f"Services not ready within {timeout}s: {missing}")


@pytest.fixture(scope="session")
def test_app_client(test_compose_stack: DockerCompose) -> Generator[httpx.AsyncClient, None, None]:
    """HTTP client for test application."""
    base_url = "http://localhost:8001"

    async def get_client():
        return httpx.AsyncClient(base_url=base_url, timeout=30.0)

    loop = asyncio.get_event_loop()
    client = loop.run_until_complete(get_client())

    yield client

    loop.run_until_complete(client.aclose())


@pytest.fixture(scope="session")
    """URLs for mock LLM provider services."""
    return {
        "gemini": "http://localhost:8002",
        "openai": "http://localhost:8003",
        "ollama": "http://localhost:11434",
    }


    """HTTP client for mock Gemini service."""
    async with httpx.AsyncClient(base_url=mock_providers["gemini"], timeout=10.0) as client:
        # Reset state before each test
        await client.post("/test-control/reset")
        yield client


    """HTTP client for mock OpenAI service."""
    async with httpx.AsyncClient(base_url=mock_providers["openai"], timeout=10.0) as client:
        # Reset state before each test
        await client.post("/test-control/reset")
        yield client


    """HTTP client for mock Ollama service."""
    async with httpx.AsyncClient(base_url=mock_providers["ollama"], timeout=10.0) as client:
        # Reset state before each test
        await client.post("/test-control/reset")
        yield client


def test_settings() -> Settings:
    """Test configuration settings."""
    return Settings(
        environment="testing",
        redis_url="redis://localhost:6380/1",
        google_api_key="test-key",
        gemini_model="gemini-2.5-pro",
        max_file_size=10485760,  # 10MB
        enable_usage_tracking=False,
        log_level="DEBUG",
    )


def sample_tender_document() -> bytes:
    """Sample tender document content for testing."""
    # This would normally be a real PDF, but for testing we'll use text
    content = """
    TENDER NOTICE
    Detailed specifications and requirements are available in the attached documentation.
    All proposals must be submitted through the electronic procurement system.
    """
    return content.encode("utf-8")


    """Multiple sample documents for batch testing."""
    documents = {}

    for i in range(5):
        content = f"""
        TENDER NOTICE {i+1}
        This is a sample tender document for testing batch processing functionality.
        Project requires expertise in infrastructure development and maintenance.
        """
        documents[f"tender_{i+1}.txt"] = content.encode("utf-8")

    return documents




# Pytest marks for test categorization
pytest.register_assert_rewrite_hook = lambda config: None


# Custom markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: Integration tests requiring containers")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "e2e: End-to-end workflow tests")
    config.addinivalue_line("markers", "performance: Performance and load tests")
    config.addinivalue_line("markers", "failover: Provider failover scenario tests")
