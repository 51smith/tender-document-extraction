"""Large batch processing integration tests."""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List

import httpx
import pytest

from tests.fixtures.test_data_manager import test_data_manager


@pytest.mark.integration()
@pytest.mark.slow()
@pytest.mark.integration
@pytest.mark.slow
class TestLargeBatchProcessing:
    """Test large batch processing capabilities."""

    async def test_medium_batch_processing(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test processing of medium-sized batches (20-50 documents)."""

        batch_size = 25
        documents = self._generate_batch_documents(batch_size)

        # Submit batch
        files = [
            ("files", (f"doc_{i}.txt", content, "text/plain"))
            for i, content in enumerate(documents)
        ]

        batch_data = {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "batch_processing_mode": "parallel",
            "max_concurrent": 5,
        }

        start_time = time.time()
        response = await test_app_client.post("/api/v1/extract/batch", files=files, data=batch_data)

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Monitor progress
        completed = await self._wait_for_batch_completion(test_app_client, job_id, timeout=120)
        processing_time = time.time() - start_time

        # Verify results
        assert completed["status"] == "completed"
        assert len(completed["results"]) == batch_size

        # Verify processing metrics
        successful_count = sum(1 for r in completed["results"] if r["status"] == "success")
        assert successful_count >= batch_size * 0.9  # At least 90% success rate

        # Performance validation
        assert processing_time < 180  # Should complete within 3 minutes
        avg_time_per_doc = processing_time / batch_size
        assert avg_time_per_doc < 10  # Less than 10 seconds per document on average

        # Check mock server stats
        stats = await mock_gemini_client.get("/test-control/stats")
        stats_data = stats.json()
        assert stats_data["request_count"] >= batch_size

    async def test_large_batch_processing(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test processing of large batches (100+ documents)."""

        batch_size = 100
        documents = self._generate_batch_documents(batch_size, complexity="simple")

        # Submit large batch
        files = [
            ("files", (f"large_doc_{i}.txt", content, "text/plain"))
            for i, content in enumerate(documents)
        ]

        batch_data = {
            "provider": "gemini",
            "model": "gemini-2.5-flash",  # Use faster model for large batches
            "batch_processing_mode": "parallel",
            "max_concurrent": 10,
            "chunk_size": 20,  # Process in chunks
        }

        start_time = time.time()
        response = await test_app_client.post("/api/v1/extract/batch", files=files, data=batch_data)

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Monitor progress with longer timeout
        completed = await self._wait_for_batch_completion(test_app_client, job_id, timeout=600)
        processing_time = time.time() - start_time

        # Verify results
        assert completed["status"] == "completed"
        assert len(completed["results"]) == batch_size

        # Performance validation for large batch
        successful_count = sum(1 for r in completed["results"] if r["status"] == "success")
        assert successful_count >= batch_size * 0.85  # At least 85% success rate

        # Should demonstrate efficiency gains from parallelization
        assert processing_time < 900  # Should complete within 15 minutes
        avg_time_per_doc = processing_time / batch_size
        assert avg_time_per_doc < 8  # Better efficiency with parallelization

    async def test_mixed_complexity_batch(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test batch with documents of varying complexity."""

        # Create mixed complexity batch
        documents = []
        complexities = ["simple"] * 20 + ["medium"] * 15 + ["complex"] * 10

        for complexity in complexities:
            doc = test_data_manager.generate_tender_document(complexity=complexity)
            text = test_data_manager.document_to_text(doc)
            documents.append(text.encode())

        files = [
            ("files", (f"mixed_{i}.txt", content, "text/plain"))
            for i, content in enumerate(documents)
        ]

        batch_data = {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "adaptive_processing": True,  # Adapt based on document complexity
            "max_concurrent": 8,
        }

        response = await test_app_client.post("/api/v1/extract/batch", files=files, data=batch_data)

        assert response.status_code == 202
        job_id = response.json()["job_id"]

        completed = await self._wait_for_batch_completion(test_app_client, job_id, timeout=300)

        # Analyze results by complexity
        results = completed["results"]
        simple_results = results[:20]
        results[20:35]
        medium_results = results[20:35]
        complex_results = results[35:]

        # Simple documents should have high success rate and fast processing
        simple_success = sum(1 for r in simple_results if r["status"] == "success")
        assert simple_success >= 18  # 90% success for simple docs

        # Complex documents might have lower success rate but should still work
        complex_success = sum(1 for r in complex_results if r["status"] == "success")
        assert complex_success >= 8  # 80% success for complex docs

    async def test_batch_progress_tracking(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test detailed progress tracking for large batches."""

        batch_size = 30
        documents = self._generate_batch_documents(batch_size)

        files = [
            ("files", (f"progress_doc_{i}.txt", content, "text/plain"))
            for i, content in enumerate(documents)
        ]

        response = await test_app_client.post(
            "/api/v1/extract/batch",
            files=files,
            data={"provider": "gemini", "model": "gemini-2.5-pro"},
        )

        job_id = response.json()["job_id"]

        # Track progress over time
        progress_snapshots = []
        last_completed = 0

        for _ in range(50):  # Check up to 50 times
            status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
            status_data = status_response.json()

            if "progress" in status_data:
                progress = status_data["progress"]
                progress_snapshots.append(
                    {
                        "timestamp": time.time(),
                        "completed": progress.get("completed", 0),
                        "total": progress.get("total", batch_size),
                        "percentage": progress.get("percentage", 0),
                    }
                )

                # Check if progress is advancing
                current_completed = progress.get("completed", 0)
                if current_completed > last_completed:
                    last_completed = current_completed

            if status_data["status"] in ["completed", "failed"]:
                break

            await asyncio.sleep(2)

        # Verify progress tracking worked
        assert len(progress_snapshots) > 0
        assert progress_snapshots[-1]["completed"] == batch_size
        assert progress_snapshots[-1]["percentage"] == 100

        # Verify progress was monotonically increasing
        for i in range(1, len(progress_snapshots)):
            assert progress_snapshots[i]["completed"] >= progress_snapshots[i - 1]["completed"]

    async def test_batch_error_handling_and_recovery(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test error handling and recovery in large batch processing."""

        batch_size = 40
        documents = self._generate_batch_documents(batch_size)

        # Configure mock to have intermittent failures
        await mock_gemini_client.post(
            "/test-control/set-failure-mode",
            json={"mode": "rate_limit", "probability": 0.2},  # 20% failure rate
        )

        files = [
            ("files", (f"error_doc_{i}.txt", content, "text/plain"))
            for i, content in enumerate(documents)
        ]

        batch_data = {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "retry_failed": True,
            "max_retries": 2,
        }

        response = await test_app_client.post("/api/v1/extract/batch", files=files, data=batch_data)

        job_id = response.json()["job_id"]
        completed = await self._wait_for_batch_completion(test_app_client, job_id, timeout=240)

        # Should still achieve high success rate due to retries
        successful_count = sum(1 for r in completed["results"] if r["status"] == "success")
        assert successful_count >= batch_size * 0.8  # At least 80% success with retries

        # Check that some documents required retries
        retry_stats = await mock_gemini_client.get("/test-control/stats")
        total_requests = retry_stats.json()["request_count"]

        # Should have made more requests than documents due to retries
        assert total_requests > batch_size

        await mock_gemini_client.post("/test-control/reset")

    async def test_batch_memory_efficiency(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test memory efficiency with large batches."""

        # Create batch with larger documents
        batch_size = 50
        documents = []

        for _i in range(batch_size):
        for i in range(batch_size):
            doc = test_data_manager.generate_tender_document(complexity="medium")
            text = test_data_manager.document_to_text(doc)
            # Add extra content to make documents larger
            extended_text = text + "\n" + "Additional content. " * 200
            documents.append(extended_text.encode())

        files = [
            ("files", (f"large_content_{i}.txt", content, "text/plain"))
            for i, content in enumerate(documents)
        ]

        batch_data = {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "streaming_processing": True,  # Process documents in streaming mode
            "max_concurrent": 5,
        }

        response = await test_app_client.post("/api/v1/extract/batch", files=files, data=batch_data)

        job_id = response.json()["job_id"]
        completed = await self._wait_for_batch_completion(test_app_client, job_id, timeout=300)

        # Should complete successfully despite large document size
        assert completed["status"] == "completed"
        successful_count = sum(1 for r in completed["results"] if r["status"] == "success")
        assert successful_count >= batch_size * 0.85

    async def test_batch_result_export_formats(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test exporting large batch results in different formats."""

        batch_size = 30
        documents = self._generate_batch_documents(batch_size, complexity="simple")

        files = [
            ("files", (f"export_doc_{i}.txt", content, "text/plain"))
            for i, content in enumerate(documents)
        ]

        response = await test_app_client.post(
            "/api/v1/extract/batch",
            files=files,
            data={"provider": "gemini", "model": "gemini-2.5-pro"},
        )

        job_id = response.json()["job_id"]
        await self._wait_for_batch_completion(test_app_client, job_id, timeout=180)

        # Test different export formats
        export_formats = ["json", "csv", "xlsx"]

        for fmt in export_formats:
            export_response = await test_app_client.get(
                f"/api/v1/jobs/{job_id}/download?format={fmt}"
            )

            if fmt == "json":
                # JSON should always be supported
                assert export_response.status_code == 200
                export_data = export_response.json()
                assert len(export_data) == batch_size
            else:
                # Other formats may or may not be implemented
                assert export_response.status_code in [200, 404, 501]

    def _generate_batch_documents(self, count: int, complexity: str = "medium") -> list[bytes]:
    def _generate_batch_documents(self, count: int, complexity: str = "medium") -> List[bytes]:
        """Generate a batch of test documents."""
        documents = []
        domains = ["construction", "technology", "healthcare"]

        for i in range(count):
            domain = domains[i % len(domains)]
            doc = test_data_manager.generate_tender_document(complexity=complexity, domain=domain)
            text = test_data_manager.document_to_text(doc)
            documents.append(text.encode())

        return documents

    async def _wait_for_batch_completion(
        self, client: httpx.AsyncClient, job_id: str, timeout: int = 300
    ) -> dict:
    ) -> Dict:
        """Wait for batch job completion with timeout."""
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            response = await client.get(f"/api/v1/jobs/{job_id}")
            data = response.json()

            if data["status"] in ["completed", "failed"]:
                return data

            await asyncio.sleep(2)

        raise TimeoutError(f"Batch job {job_id} did not complete within {timeout} seconds")


@pytest.mark.integration()
@pytest.mark.slow()
@pytest.mark.performance()
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.performance
class TestBatchProcessingPerformance:
    """Test batch processing performance characteristics."""

    async def test_concurrent_batch_jobs(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Test running multiple batch jobs concurrently."""

        batch_size = 10
        num_jobs = 3

        # Submit multiple batch jobs concurrently
        job_ids = []

        for job_num in range(num_jobs):
            documents = []
            for _i in range(batch_size):
            for i in range(batch_size):
                doc = test_data_manager.generate_tender_document()
                text = test_data_manager.document_to_text(doc)
                documents.append(text.encode())

            files = [
                ("files", (f"concurrent_{job_num}_{i}.txt", content, "text/plain"))
                for i, content in enumerate(documents)
            ]

            response = await test_app_client.post(
                "/api/v1/extract/batch",
                files=files,
                data={"provider": "gemini", "model": "gemini-2.5-pro"},
            )

            assert response.status_code == 202
            job_ids.append(response.json()["job_id"])

        # Wait for all jobs to complete
        completed_jobs = []
        max_wait_time = 300
        start_time = time.time()

        while len(completed_jobs) < num_jobs and (time.time() - start_time) < max_wait_time:
            for job_id in job_ids:
                if job_id in completed_jobs:
                    continue

                status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
                status_data = status_response.json()

                if status_data["status"] == "completed":
                    completed_jobs.append(job_id)
                elif status_data["status"] == "failed":
                    pytest.fail(f"Concurrent job {job_id} failed")

            await asyncio.sleep(2)

        # Verify all jobs completed successfully
        assert len(completed_jobs) == num_jobs

        # Verify each job processed all documents
        for job_id in completed_jobs:
            status_response = await test_app_client.get(f"/api/v1/jobs/{job_id}")
            status_data = status_response.json()

            assert len(status_data["results"]) == batch_size
            successful_count = sum(1 for r in status_data["results"] if r["status"] == "success")
            assert successful_count >= batch_size * 0.8

    async def test_batch_throughput_measurement(
        self, test_app_client: httpx.AsyncClient, mock_gemini_client: httpx.AsyncClient
    ):
        """Measure and validate batch processing throughput."""

        batch_size = 50
        documents = self._generate_simple_documents(batch_size)

        files = [
            ("files", (f"throughput_doc_{i}.txt", content, "text/plain"))
            for i, content in enumerate(documents)
        ]

        # Measure processing time
        start_time = time.time()

        response = await test_app_client.post(
            "/api/v1/extract/batch",
            files=files,
            data={
                "provider": "gemini",
                "model": "gemini-2.5-flash",  # Fast model for throughput test
                "max_concurrent": 10,
            },
        )

        job_id = response.json()["job_id"]
        completed = await self._wait_for_batch_completion(test_app_client, job_id, timeout=180)

        end_time = time.time()
        total_processing_time = end_time - start_time

        # Calculate throughput metrics
        successful_count = sum(1 for r in completed["results"] if r["status"] == "success")
        throughput = successful_count / total_processing_time  # documents per second

        # Validate throughput meets minimum requirements
        assert throughput >= 0.3  # At least 0.3 documents per second
        assert successful_count >= batch_size * 0.9  # 90% success rate

        # Log performance metrics for analysis
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Batch throughput: {throughput:.2f} documents/second")
        logger.info(
            f"Success rate: {successful_count}/{batch_size} "
            f"({successful_count/batch_size*100:.1f}%)"
        )
        logger.info(f"Total time: {total_processing_time:.1f} seconds")

    def _generate_simple_documents(self, count: int) -> list[bytes]:
        """Generate simple documents for performance testing."""
        documents = []

        for _i in range(count):
        print(f"Batch throughput: {throughput:.2f} documents/second")
        print(
            f"Success rate: {successful_count}/{batch_size} ({successful_count/batch_size*100:.1f}%)"
        )
        print(f"Total time: {total_processing_time:.1f} seconds")

    def _generate_simple_documents(self, count: int) -> List[bytes]:
        """Generate simple documents for performance testing."""
        documents = []

        for i in range(count):
            doc = test_data_manager.generate_tender_document(complexity="simple")
            text = test_data_manager.document_to_text(doc)
            documents.append(text.encode())

        return documents

    async def _wait_for_batch_completion(
        self, client: httpx.AsyncClient, job_id: str, timeout: int = 300
    ) -> dict:
    ) -> Dict:
        """Wait for batch job completion."""
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            response = await client.get(f"/api/v1/jobs/{job_id}")
            data = response.json()

            if data["status"] in ["completed", "failed"]:
                return data

            await asyncio.sleep(1)

        raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")
