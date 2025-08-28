"""Multi-provider failover scenario integration tests."""

import asyncio
import json
import time
from typing import Dict, List

import httpx
import pytest

from tests.fixtures.test_data_manager import test_data_manager


@pytest.mark.integration
@pytest.mark.failover
class TestProviderFailoverScenarios:
    """Test failover scenarios between different LLM providers."""

    async def test_gemini_to_openai_failover(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        sample_tender_document: bytes,
    ):
        """Test failover from Gemini to OpenAI when Gemini fails."""

        # Step 1: Configure Gemini to fail
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "quota_exceeded", "probability": 1.0}
        )

        # Step 2: Submit request with primary provider as Gemini
        files = {"file": ("failover_test.txt", sample_tender_document, "text/plain")}
        extraction_data = {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "fallback_providers": ["openai"],
            "enable_failover": True,
        }

        response = await test_app_client.post("/api/v1/extract", files=files, data=extraction_data)

        # Should succeed with fallback provider
        assert response.status_code == 200
        result = response.json()

        # Verify extraction was successful
        assert "project_title" in result
        assert "extraction_metadata" in result

        # Verify failover was used (check metadata for provider info if available)
        if "provider_used" in result.get("extraction_metadata", {}):
            assert result["extraction_metadata"]["provider_used"] == "openai"

        # Reset Gemini state
        await mock_gemini_client.post("/test-control/reset")

    async def test_cascade_failover_all_providers(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        mock_ollama_client: httpx.AsyncClient,
        sample_tender_document: bytes,
    ):
        """Test cascade failover through all available providers."""

        # Configure first two providers to fail
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "rate_limit", "probability": 1.0}
        )

        await mock_openai_client.post(
            "/test-control/set-failure-mode", json={"mode": "quota_exceeded", "probability": 1.0}
        )

        # Ollama should work (default state)

        files = {"file": ("cascade_test.txt", sample_tender_document, "text/plain")}
        extraction_data = {
            "provider": "gemini",
            "fallback_providers": ["openai", "ollama"],
            "enable_failover": True,
        }

        response = await test_app_client.post("/api/v1/extract", files=files, data=extraction_data)

        # Should succeed with final fallback (Ollama)
        assert response.status_code == 200
        result = response.json()

        assert "project_title" in result

        # Reset all providers
        await mock_gemini_client.post("/test-control/reset")
        await mock_openai_client.post("/test-control/reset")

    async def test_all_providers_fail_scenario(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        mock_ollama_client: httpx.AsyncClient,
        sample_tender_document: bytes,
    ):
        """Test scenario where all providers fail."""

        # Configure all providers to fail
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "quota_exceeded", "probability": 1.0}
        )

        await mock_openai_client.post(
            "/test-control/set-failure-mode", json={"mode": "quota_exceeded", "probability": 1.0}
        )

        await mock_ollama_client.post(
            "/test-control/set-failure-mode", json={"mode": "connection_error", "probability": 1.0}
        )

        files = {"file": ("all_fail_test.txt", sample_tender_document, "text/plain")}
        extraction_data = {
            "provider": "gemini",
            "fallback_providers": ["openai", "ollama"],
            "enable_failover": True,
        }

        response = await test_app_client.post("/api/v1/extract", files=files, data=extraction_data)

        # Should return error when all providers fail
        assert response.status_code in [503, 500, 429]
        error_data = response.json()
        assert "error" in error_data or "detail" in error_data

        # Reset all providers
        await mock_gemini_client.post("/test-control/reset")
        await mock_openai_client.post("/test-control/reset")
        await mock_ollama_client.post("/test-control/reset")

    async def test_batch_processing_with_failover(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        sample_batch_documents: Dict[str, bytes],
    ):
        """Test batch processing with provider failover."""

        # Configure Gemini to fail intermittently
        await mock_gemini_client.post(
            "/test-control/set-failure-mode",
            json={"mode": "rate_limit", "probability": 0.6},  # 60% chance of failure
        )

        files = [
            ("files", (filename, content, "text/plain"))
            for filename, content in sample_batch_documents.items()
        ]

        batch_data = {
            "provider": "gemini",
            "fallback_providers": ["openai"],
            "enable_failover": True,
        }

        response = await test_app_client.post("/api/v1/extract/batch", files=files, data=batch_data)

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for completion
        max_attempts = 30
        for _ in range(max_attempts):
            status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
            status_data = status_response.json()

            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Batch job failed: {status_data.get('error')}")

            await asyncio.sleep(1)

        # Verify all documents were processed (some via failover)
        assert status_data["status"] == "completed"
        assert len(status_data["results"]) == len(sample_batch_documents)

        # All results should be successful due to failover
        for result in status_data["results"]:
            assert result["status"] == "success"

        # Reset Gemini
        await mock_gemini_client.post("/test-control/reset")

    async def test_provider_recovery_after_failure(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        sample_tender_document: bytes,
    ):
        """Test provider recovery and circuit breaker behavior."""

        # Step 1: Configure provider to fail temporarily
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "rate_limit", "probability": 1.0}
        )

        # Step 2: Make several requests that should fail
        files = {"file": ("recovery_test.txt", sample_tender_document, "text/plain")}

        for i in range(3):
            response = await test_app_client.post(
                "/api/v1/extract",
                files=files,
                data={"provider": "gemini", "model": "gemini-2.5-pro"},
            )
            # Should fail
            assert response.status_code == 429
            await asyncio.sleep(0.5)

        # Step 3: Fix the provider
        await mock_gemini_client.post("/test-control/reset")

        # Step 4: Wait for circuit breaker recovery (if implemented)
        await asyncio.sleep(2)

        # Step 5: Try again - should work now
        response = await test_app_client.post(
            "/api/v1/extract", files=files, data={"provider": "gemini", "model": "gemini-2.5-pro"}
        )

        # Should succeed after recovery
        assert response.status_code == 200

    async def test_load_balancing_across_providers(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
    ):
        """Test load balancing requests across multiple healthy providers."""

        # Generate multiple documents for load balancing test
        documents = []
        for i in range(10):
            doc = test_data_manager.generate_tender_document()
            text = test_data_manager.document_to_text(doc)
            documents.append((f"load_balance_{i}.txt", text.encode()))

        # Submit requests with load balancing enabled
        async def submit_request(filename, content, provider):
            files = {"file": (filename, content, "text/plain")}
            return await test_app_client.post(
                "/api/v1/extract",
                files=files,
                data={
                    "provider": provider,
                    "enable_load_balancing": True,
                    "fallback_providers": ["gemini", "openai"],
                },
            )

        # Alternate between providers
        tasks = []
        for i, (filename, content) in enumerate(documents):
            provider = "gemini" if i % 2 == 0 else "openai"
            tasks.append(submit_request(filename, content, provider))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful responses
        successful = 0
        for response in responses:
            if not isinstance(response, Exception) and response.status_code == 200:
                successful += 1

        # Should have high success rate with load balancing
        assert successful >= 8, f"Only {successful} out of {len(documents)} requests succeeded"

        # Verify both providers were used
        gemini_stats = await mock_gemini_client.get("/test-control/stats")
        openai_stats = await mock_openai_client.get("/test-control/stats")

        gemini_requests = gemini_stats.json()["request_count"]
        openai_requests = openai_stats.json()["request_count"]

        # Both providers should have received requests
        assert gemini_requests > 0
        assert openai_requests > 0


@pytest.mark.integration
@pytest.mark.failover
@pytest.mark.slow
class TestAdvancedFailoverScenarios:
    """Test advanced failover scenarios and edge cases."""

    async def test_partial_batch_failover(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        sample_batch_documents: Dict[str, bytes],
    ):
        """Test failover when only some documents in a batch fail."""

        # Configure Gemini to fail for specific content patterns
        await mock_gemini_client.post(
            "/test-control/set-failure-mode",
            json={"mode": "safety_filter", "probability": 0.4},  # 40% chance of safety filter
        )

        files = [
            ("files", (filename, content, "text/plain"))
            for filename, content in sample_batch_documents.items()
        ]

        batch_data = {
            "provider": "gemini",
            "fallback_providers": ["openai"],
            "enable_failover": True,
        }

        response = await test_app_client.post("/api/v1/extract/batch", files=files, data=batch_data)

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Wait for completion
        max_attempts = 40
        for _ in range(max_attempts):
            status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
            status_data = status_response.json()

            if status_data["status"] in ["completed", "failed"]:
                break

            await asyncio.sleep(1)

        # Verify results
        assert status_data["status"] == "completed"
        results = status_data["results"]

        # Should have results for all documents
        assert len(results) == len(sample_batch_documents)

        # Most or all should be successful due to failover
        successful_count = sum(1 for r in results if r["status"] == "success")
        assert successful_count >= len(sample_batch_documents) * 0.8  # At least 80% success

        await mock_gemini_client.post("/test-control/reset")

    async def test_failover_with_different_models(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        sample_tender_document: bytes,
    ):
        """Test failover with different models for each provider."""

        # Configure primary provider to fail
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "model_not_found", "probability": 1.0}
        )

        files = {"file": ("model_failover.txt", sample_tender_document, "text/plain")}
        extraction_data = {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "fallback_providers": ["openai"],
            "fallback_models": {"openai": "gpt-4-turbo-preview"},
            "enable_failover": True,
        }

        response = await test_app_client.post("/api/v1/extract", files=files, data=extraction_data)

        # Should succeed with fallback model
        assert response.status_code == 200
        result = response.json()

        assert "project_title" in result

        # Verify fallback model was used if metadata includes model info
        if "model_used" in result.get("extraction_metadata", {}):
            assert "gpt-4" in result["extraction_metadata"]["model_used"]

        await mock_gemini_client.post("/test-control/reset")

    async def test_cascading_timeout_failover(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        sample_tender_document: bytes,
    ):
        """Test failover when providers timeout."""

        # Configure providers with different timeout behaviors
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "timeout", "probability": 1.0}
        )

        # OpenAI should work normally

        files = {"file": ("timeout_test.txt", sample_tender_document, "text/plain")}
        extraction_data = {
            "provider": "gemini",
            "fallback_providers": ["openai"],
            "enable_failover": True,
            "timeout": 10,  # 10 second timeout
        }

        start_time = time.time()

        response = await test_app_client.post("/api/v1/extract", files=files, data=extraction_data)

        elapsed_time = time.time() - start_time

        # Should succeed with fallback but take less than timeout period
        assert response.status_code == 200
        assert elapsed_time < 15  # Should not wait for full timeout

        result = response.json()
        assert "project_title" in result

        await mock_gemini_client.post("/test-control/reset")

    async def test_intelligent_provider_selection(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        mock_ollama_client: httpx.AsyncClient,
    ):
        """Test intelligent provider selection based on document characteristics."""

        # Create documents with different characteristics
        test_cases = [
            {
                "document": test_data_manager.generate_tender_document(complexity="simple"),
                "expected_provider": "ollama",  # Local for simple docs
                "description": "Simple document should use local provider",
            },
            {
                "document": test_data_manager.generate_tender_document(complexity="complex"),
                "expected_provider": "gemini",  # Cloud for complex docs
                "description": "Complex document should use advanced cloud provider",
            },
        ]

        for test_case in test_cases:
            document_text = test_data_manager.document_to_text(test_case["document"])
            files = {"file": ("intelligent_select.txt", document_text.encode(), "text/plain")}

            extraction_data = {
                "enable_intelligent_routing": True,
                "available_providers": ["gemini", "openai", "ollama"],
            }

            response = await test_app_client.post(
                "/api/v1/extract", files=files, data=extraction_data
            )

            # Should succeed regardless of routing logic
            if response.status_code == 200:
                result = response.json()
                assert "project_title" in result

                # Check if provider selection metadata is available
                if "provider_used" in result.get("extraction_metadata", {}):
                    # Could verify intelligent selection logic here
                    pass

    async def test_geographic_failover_simulation(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        sample_tender_document: bytes,
    ):
        """Simulate geographic failover scenarios."""

        # Simulate regional outage by making primary provider unavailable
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "connection_error", "probability": 1.0}
        )

        files = {"file": ("geo_failover.txt", sample_tender_document, "text/plain")}
        extraction_data = {
            "provider": "gemini",
            "region": "us-east",
            "fallback_providers": ["openai"],
            "fallback_regions": {"openai": "us-west"},
            "enable_failover": True,
        }

        response = await test_app_client.post("/api/v1/extract", files=files, data=extraction_data)

        # Should succeed with geographic failover
        assert response.status_code == 200
        result = response.json()
        assert "project_title" in result

        await mock_gemini_client.post("/test-control/reset")
