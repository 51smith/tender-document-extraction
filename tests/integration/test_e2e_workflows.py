"""End-to-end workflow integration tests."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict

import httpx
import pytest

from tests.fixtures.test_data_manager import test_data_manager


@pytest.mark.integration()
@pytest.mark.e2e()
from tests.fixtures.test_data_manager import get_sample_document, test_data_manager


@pytest.mark.integration
@pytest.mark.e2e
class TestDocumentExtractionWorkflow:
    """Test complete document extraction workflows."""

    async def test_single_document_extraction_workflow(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        sample_tender_document: bytes,
    ):
        """Test complete single document extraction workflow."""

        # Step 1: Submit document for extraction
        files = {"file": ("tender.txt", sample_tender_document, "text/plain")}
        extraction_data = {"provider": "gemini", "model": "gemini-2.5-pro", "temperature": 0.1}

        response = await test_app_client.post("/api/v1/extract", files=files, data=extraction_data)

        assert response.status_code == 200
        result = response.json()

        # Verify extraction structure
        assert "project_title" in result
        assert "estimated_value" in result
        assert "confidence_scores" in result
        assert "extraction_metadata" in result

        # Verify confidence scores are reasonable
        confidence_scores = result["confidence_scores"]
        for _field, score in confidence_scores.items():
        for field, score in confidence_scores.items():
            assert 0.0 <= score <= 1.0

        # Verify mock was called
        stats = await mock_gemini_client.get("/test-control/stats")
        stats_data = stats.json()
        assert stats_data["request_count"] >= 1

    async def test_batch_processing_workflow(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        sample_batch_documents: dict[str, bytes],
        sample_batch_documents: Dict[str, bytes],
    ):
        """Test complete batch processing workflow."""

        # Step 1: Submit batch job
        files = [
            ("files", (filename, content, "text/plain"))
            for filename, content in sample_batch_documents.items()
        ]
        batch_data = {"provider": "gemini", "model": "gemini-2.5-pro"}

        response = await test_app_client.post("/api/v1/extract/batch", files=files, data=batch_data)

        assert response.status_code == 202
        batch_result = response.json()
        job_id = batch_result["job_id"]

        # Step 2: Poll job status until completion
        max_attempts = 30
        for _attempt in range(max_attempts):
        for attempt in range(max_attempts):
            status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
            assert status_response.status_code == 200

            status_data = status_response.json()

            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Batch job failed: {status_data.get('error')}")

            await asyncio.sleep(1)
        else:
            pytest.fail("Batch job did not complete within expected time")

        # Step 3: Verify results
        assert status_data["status"] == "completed"
        assert "results" in status_data
        assert len(status_data["results"]) == len(sample_batch_documents)

        # Verify each document was processed
        for result in status_data["results"]:
            assert result["status"] == "success"
            assert "extraction_result" in result
            assert "confidence_scores" in result["extraction_result"]

        # Step 4: Test result download
        download_response = await test_app_client.get(f"/api/v1/jobs/{job_id}/download?format=json")
        assert download_response.status_code == 200

        download_data = download_response.json()
        assert len(download_data) == len(sample_batch_documents)

    async def test_error_handling_workflow(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test error handling in extraction workflow."""

        # Configure mock to return errors
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "rate_limit", "probability": 1.0}
        )

        # Submit document that should trigger error
        test_document = b"Test document for error handling"
        files = {"file": ("error_test.txt", test_document, "text/plain")}

        response = await test_app_client.post(
            "/api/v1/extract", files=files, data={"provider": "gemini", "model": "gemini-2.5-pro"}
        )

        # Should return error status
        assert response.status_code == 429  # Rate limit error

        # Reset mock state
        await mock_gemini_client.post("/test-control/reset")

    async def test_large_document_workflow(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test workflow with large documents."""

        # Generate large document
        large_document = test_data_manager.generate_tender_document(complexity="complex")
        large_text = test_data_manager.document_to_text(large_document)

        # Add more content to make it realistically large
        extended_text = large_text + "\n\n" + "Additional requirements and specifications. " * 500

        files = {"file": ("large_tender.txt", extended_text.encode(), "text/plain")}

        response = await test_app_client.post(
            "/api/v1/extract",
            files=files,
            data={"provider": "gemini", "model": "gemini-2.5-pro", "temperature": 0.1},
        )

        assert response.status_code == 200
        result = response.json()

        # Verify that large document was processed successfully
        assert "project_title" in result
        assert result["extraction_metadata"]["processing_time"] > 0

    async def test_multi_format_document_workflow(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test workflow with different document formats."""

        # Test with different content types
        test_cases = [
            ("text/plain", b"Plain text tender document"),
            ("application/pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nMock PDF content"),
            ("text/html", b"<html><body>HTML tender document</body></html>"),
        ]

        for content_type, content in test_cases:
            files = {"file": (f"test.{content_type.split('/')[-1]}", content, content_type)}

            response = await test_app_client.post(
                "/api/v1/extract",
                files=files,
                data={"provider": "gemini", "model": "gemini-2.5-pro"},
            )

            # Should handle different formats appropriately
            if content_type == "text/plain":
                assert response.status_code == 200
            # Other formats might be rejected or processed differently
            # This depends on implementation specifics


@pytest.mark.integration()
@pytest.mark.e2e()
@pytest.mark.integration
@pytest.mark.e2e
class TestJobManagementWorkflow:
    """Test job management workflows."""

    async def test_job_lifecycle_workflow(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        sample_batch_documents: dict[str, bytes],
        sample_batch_documents: Dict[str, bytes],
    ):
        """Test complete job lifecycle from creation to cleanup."""

        # Step 1: Create job
        files = [
            ("files", (filename, content, "text/plain"))
            for filename, content in list(sample_batch_documents.items())[:2]  # Use fewer for speed
        ]

        response = await test_app_client.post(
            "/api/v1/extract/batch", files=files, data={"provider": "gemini"}
        )

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Step 2: Check job appears in job list
        jobs_response = await test_app_client.get("/api/v1/jobs")
        assert jobs_response.status_code == 200

        jobs_data = jobs_response.json()
        job_ids = [job["job_id"] for job in jobs_data["jobs"]]
        assert job_id in job_ids

        # Step 3: Monitor job progress
        progress_updates = []
        max_attempts = 20

        for _ in range(max_attempts):
            status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
            status_data = status_response.json()
            progress_updates.append(status_data["status"])

            if status_data["status"] in ["completed", "failed"]:
                break

            await asyncio.sleep(0.5)

        # Step 4: Verify job completed successfully
        assert status_data["status"] == "completed"
        assert (
            "processing" in progress_updates or "running" in progress_updates
        )  # Job went through processing

        # Step 5: Download results in different formats
        formats = ["json", "csv", "xlsx"]

        for fmt in formats:
            download_response = await test_app_client.get(
                f"/api/v1/jobs/{job_id}/download?format={fmt}"
            )
            if fmt == "json":
                assert download_response.status_code == 200
            # Other formats may or may not be implemented

    async def test_job_cancellation_workflow(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test job cancellation workflow."""

        # Configure mock to be slow
        await mock_gemini_client.post(
            "/test-control/set-failure-mode", json={"mode": "timeout", "probability": 0.5}
        )

        # Create a job with multiple files
        files = []
        for i in range(5):
            content = f"Test document {i} with extended content for processing delay"
            files.append(("files", (f"test_{i}.txt", content.encode(), "text/plain")))

        response = await test_app_client.post(
            "/api/v1/extract/batch", files=files, data={"provider": "gemini"}
        )

        job_id = response.json()["job_id"]

        # Wait a bit for job to start
        await asyncio.sleep(1)

        # Cancel the job
        cancel_response = await test_app_client.post(f"/api/v1/jobs/{job_id}/cancel")

        # Verify cancellation response (may vary based on implementation)
        assert cancel_response.status_code in [200, 404]  # 404 if job already completed

        # Reset mock
        await mock_gemini_client.post("/test-control/reset")


@pytest.mark.integration()
@pytest.mark.e2e()
@pytest.mark.integration
@pytest.mark.e2e
class TestSystemHealthWorkflow:
    """Test system health and monitoring workflows."""

    async def test_health_check_workflow(
        self, test_app_client: httpx.AsyncClient, mock_providers: dict[str, str]
        self, test_app_client: httpx.AsyncClient, mock_providers: Dict[str, str]
    ):
        """Test comprehensive health check workflow."""

        # Basic health check
        health_response = await test_app_client.get("/health")
        assert health_response.status_code == 200

        health_data = health_response.json()
        assert health_data["status"] in ["healthy", "degraded"]
        assert "timestamp" in health_data
        assert "services" in health_data

        # Verify service health statuses
        services = health_data["services"]
        assert "database" in services  # Redis
        assert "llm_providers" in services

        # Test individual provider health
        if "llm_providers" in services:
            for _provider, status in services["llm_providers"].items():
            for provider, status in services["llm_providers"].items():
                assert status in ["healthy", "unhealthy", "unknown"]

    async def test_metrics_collection_workflow(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test metrics collection and reporting workflow."""

        # Perform some operations to generate metrics
        test_document = b"Test document for metrics collection"
        files = {"file": ("metrics_test.txt", test_document, "text/plain")}

        # Make several requests
        for _ in range(3):
            await test_app_client.post(
                "/api/v1/extract",
                files=files,
                data={"provider": "gemini", "model": "gemini-2.5-pro"},
            )

        # Check usage statistics
        stats_response = await test_app_client.get("/api/v1/statistics")

        if stats_response.status_code == 200:  # May not be implemented yet
            stats_data = stats_response.json()
            assert "total_extractions" in stats_data
            assert stats_data["total_extractions"] >= 3

        # Check if usage tracking is working
        usage_response = await test_app_client.get("/api/v1/usage")

        if usage_response.status_code == 200:  # May not be implemented yet
            usage_data = usage_response.json()
            # Verify usage data structure
            assert isinstance(usage_data, dict)


@pytest.mark.integration()
@pytest.mark.e2e()
@pytest.mark.slow()
@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.slow
class TestComplexWorkflowScenarios:
    """Test complex, realistic workflow scenarios."""

    async def test_mixed_provider_workflow(
        self,
        test_app_client: httpx.AsyncClient,
        mock_gemini_client: httpx.AsyncClient,
        mock_openai_client: httpx.AsyncClient,
        sample_batch_documents: dict[str, bytes],
        sample_batch_documents: Dict[str, bytes],
    ):
        """Test workflow using different providers for different documents."""

        providers = ["gemini", "openai"]
        jobs = []

        # Submit jobs to different providers
        for i, provider in enumerate(providers):
            # Use subset of documents for each provider
            subset_docs = dict(list(sample_batch_documents.items())[i * 2 : (i + 1) * 2])

            files = [
                ("files", (filename, content, "text/plain"))
                for filename, content in subset_docs.items()
            ]

            response = await test_app_client.post(
                "/api/v1/extract/batch", files=files, data={"provider": provider}
            )

            assert response.status_code == 202
            jobs.append((response.json()["job_id"], provider))

        # Wait for all jobs to complete
        completed_jobs = []
        max_wait_time = 30
        start_time = time.time()

        while len(completed_jobs) < len(jobs) and (time.time() - start_time) < max_wait_time:
            for job_id, provider in jobs:
                if job_id in [completed[0] for completed in completed_jobs]:
                    continue

                status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
                status_data = status_response.json()

                if status_data["status"] == "completed":
                    completed_jobs.append((job_id, provider))
                elif status_data["status"] == "failed":
                    pytest.fail(f"Job {job_id} with provider {provider} failed")

            await asyncio.sleep(1)

        # Verify all jobs completed
        assert len(completed_jobs) == len(jobs)

        # Verify results from different providers
        for job_id, provider in completed_jobs:
            status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
            status_data = status_response.json()

            assert status_data["status"] == "completed"
            assert len(status_data["results"]) == 2  # 2 documents per job

    async def test_concurrent_requests_workflow(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test handling of concurrent extraction requests."""

        # Generate multiple test documents
        documents = []
        for i in range(10):
            doc = test_data_manager.generate_tender_document()
            text = test_data_manager.document_to_text(doc)
            documents.append((f"concurrent_{i}.txt", text.encode()))

        # Submit all requests concurrently
        async def submit_extraction(filename, content):
            files = {"file": (filename, content, "text/plain")}
            return await test_app_client.post(
                "/api/v1/extract",
                files=files,
                data={"provider": "gemini", "model": "gemini-2.5-pro"},
            )

        # Execute concurrent requests
        tasks = [submit_extraction(filename, content) for filename, content in documents]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify responses
        successful_responses = 0
        for response in responses:
            if isinstance(response, Exception):
                # Some failures may be expected under high concurrency
                continue

            if response.status_code == 200:
                successful_responses += 1
            elif response.status_code == 429:  # Rate limited
                # This is expected under high load
                continue

        # Should have at least some successful responses
        assert (
            successful_responses >= 5
        ), f"Only {successful_responses} out of {len(documents)} requests succeeded"
