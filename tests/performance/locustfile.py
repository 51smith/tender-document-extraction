"""Locust load testing configuration for tender extraction service."""

import json
import random

# Import test data manager
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from locust import HttpUser, between, events, task

sys.path.append(str(Path(__file__).parent.parent))
from fixtures.test_data_manager import test_data_manager


class TenderExtractionUser(HttpUser):
    """Simulates a user performing document extraction operations."""

    wait_time = between(1, 5)  # Wait 1-5 seconds between requests

    def on_start(self):
        """Initialize user session."""
        self.test_documents = self._generate_test_documents()
        self.job_ids = []  # Track submitted jobs

    @task(3)
    def single_document_extraction(self):
        """Perform single document extraction (most common operation)."""
        document = random.choice(self.test_documents)

        files = {"file": ("test_document.txt", document, "text/plain")}
        data = {
            "provider": random.choice(["gemini", "openai"]),
            "model": random.choice(["gemini-2.5-pro", "gpt-4-turbo-preview"]),
            "temperature": 0.1,
        }

        with self.client.post(
            "/api/v1/extract", files=files, data=data, catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()
                # Validate response structure
                if all(field in result for field in ["project_title", "confidence_scores"]):
                    response.success()
                else:
                    response.failure("Invalid response structure")
            elif response.status_code == 429:
                response.success()  # Rate limiting is expected under load
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(1)
    def batch_processing(self):
        """Perform batch document processing (less frequent but important)."""
        # Select subset of documents for batch
        batch_docs = random.sample(self.test_documents, min(5, len(self.test_documents)))

        files = [
            ("files", (f"batch_doc_{i}.txt", doc, "text/plain")) for i, doc in enumerate(batch_docs)
        ]

        data = {
            "provider": random.choice(["gemini", "openai"]),
            "model": random.choice(["gemini-2.5-pro", "gpt-4-turbo-preview"]),
        }

        with self.client.post(
            "/api/v1/extract/batch", files=files, data=data, catch_response=True
        ) as response:
            if response.status_code == 202:
                result = response.json()
                if "job_id" in result:
                    self.job_ids.append(result["job_id"])
                    response.success()
                else:
                    response.failure("No job_id in batch response")
            else:
                response.failure(f"Batch submission failed: {response.status_code}")

    @task(2)
    def check_job_status(self):
        """Check status of submitted batch jobs."""
        if not self.job_ids:
            return

        job_id = random.choice(self.job_ids)

        with self.client.get(f"/api/v1/jobs/{job_id}", catch_response=True) as response:
            if response.status_code == 200:
                result = response.json()
                if "status" in result:
                    if result["status"] == "completed":
                        # Remove completed jobs from tracking
                        self.job_ids.remove(job_id)
                    response.success()
                else:
                    response.failure("No status in job response")
            elif response.status_code == 404:
                # Job not found, remove from tracking
                self.job_ids.remove(job_id)
                response.success()
            else:
                response.failure(f"Job status check failed: {response.status_code}")

    @task(1)
    def list_jobs(self):
        """List all jobs for the user."""
        with self.client.get("/api/v1/jobs", catch_response=True) as response:
            if response.status_code == 200:
                result = response.json()
                if "jobs" in result and isinstance(result["jobs"], list):
                    response.success()
                else:
                    response.failure("Invalid jobs list response")
            else:
                response.failure(f"Jobs list failed: {response.status_code}")

    @task(1)
    def health_check(self):
        """Check system health."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                result = response.json()
                if "status" in result:
                    response.success()
                else:
                    response.failure("Invalid health response")
            else:
                response.failure(f"Health check failed: {response.status_code}")

    def _generate_test_documents(self) -> List[bytes]:
        """Generate test documents for load testing."""
        documents = []

        # Generate documents of varying complexity
        for complexity in ["simple", "medium", "complex"]:
            for domain in ["construction", "technology", "healthcare"]:
                for _ in range(2):  # 2 documents per complexity-domain combination
                    doc = test_data_manager.generate_tender_document(
                        complexity=complexity, domain=domain
                    )
                    text = test_data_manager.document_to_text(doc)
                    documents.append(text.encode())

        return documents


class HighVolumeUser(TenderExtractionUser):
    """User that generates high volume of requests for stress testing."""

    wait_time = between(0.1, 1)  # Very short wait times

    @task(5)
    def rapid_single_extractions(self):
        """Perform rapid single document extractions."""
        super().single_document_extraction()

    @task(1)
    def concurrent_batch_submissions(self):
        """Submit multiple small batches rapidly."""
        # Submit smaller batches more frequently
        batch_docs = random.sample(self.test_documents, min(3, len(self.test_documents)))

        files = [
            ("files", (f"stress_doc_{i}.txt", doc, "text/plain"))
            for i, doc in enumerate(batch_docs)
        ]

        data = {"provider": "gemini", "model": "gemini-2.5-flash"}  # Use fast model

        with self.client.post(
            "/api/v1/extract/batch", files=files, data=data, catch_response=True
        ) as response:
            if response.status_code in [202, 429]:  # Accept rate limiting
                response.success()
            else:
                response.failure(f"Stress batch failed: {response.status_code}")


class APIConsistencyUser(HttpUser):
    """User focused on testing API consistency and reliability."""

    wait_time = between(2, 8)

    def on_start(self):
        """Initialize consistency testing."""
        self.baseline_document = self._create_baseline_document()
        self.baseline_result = None

    @task(3)
    def consistency_check_extraction(self):
        """Check extraction consistency for the same document."""
        files = {"file": ("consistency_test.txt", self.baseline_document, "text/plain")}
        data = {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "temperature": 0.0,  # Deterministic output
        }

        with self.client.post(
            "/api/v1/extract", files=files, data=data, catch_response=True
        ) as response:
            if response.status_code == 200:
                result = response.json()

                if self.baseline_result is None:
                    self.baseline_result = result
                    response.success()
                else:
                    # Check consistency with baseline
                    consistency_score = self._calculate_consistency(self.baseline_result, result)
                    if consistency_score > 0.8:  # 80% consistency threshold
                        response.success()
                    else:
                        response.failure(f"Consistency check failed: {consistency_score:.2f}")
            else:
                response.failure(f"Consistency test failed: {response.status_code}")

    @task(1)
    def cross_provider_consistency(self):
        """Test consistency across different providers."""
        providers = ["gemini", "openai"]
        results = {}

        for provider in providers:
            files = {"file": ("cross_provider_test.txt", self.baseline_document, "text/plain")}
            data = {
                "provider": provider,
                "model": "gemini-2.5-pro" if provider == "gemini" else "gpt-4-turbo-preview",
                "temperature": 0.0,
            }

            with self.client.post(
                "/api/v1/extract",
                files=files,
                data=data,
                catch_response=True,
                name=f"/api/v1/extract/{provider}",
            ) as response:
                if response.status_code == 200:
                    results[provider] = response.json()
                    response.success()
                else:
                    response.failure(f"Cross-provider test failed for {provider}")
                    return

        # Compare results across providers
        if len(results) == 2:
            provider1, provider2 = list(results.keys())
            consistency = self._calculate_consistency(results[provider1], results[provider2])
            # Cross-provider consistency can be lower than same-provider
            if consistency > 0.6:  # 60% consistency threshold
                pass  # Success already recorded above
            else:
                # Log inconsistency for analysis
                print(f"Cross-provider consistency low: {consistency:.2f}")

    def _create_baseline_document(self) -> bytes:
        """Create a stable baseline document for consistency testing."""
        doc = test_data_manager.generate_tender_document(complexity="medium")
        # Use a fixed seed or predefined content for consistency
        doc.project_title = "Infrastructure Development Project Alpha"
        doc.estimated_value = 2500000.0
        doc.currency = "EUR"

        text = test_data_manager.document_to_text(doc)
        return text.encode()

    def _calculate_consistency(self, result1: Dict, result2: Dict) -> float:
        """Calculate consistency score between two extraction results."""
        if not result1 or not result2:
            return 0.0

        # Compare key fields
        key_fields = ["project_title", "estimated_value", "currency"]
        matches = 0
        total = 0

        for field in key_fields:
            if field in result1 and field in result2:
                total += 1
                if result1[field] == result2[field]:
                    matches += 1

        return matches / total if total > 0 else 0.0


# Custom events and monitoring
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize test monitoring."""
    print("Starting load test...")
    environment.stats.csv_writer.response_times_file.write(
        "timestamp,name,response_time,response_length,error\n"
    )


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Cleanup and final reporting."""
    print(f"Load test completed. Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")


# Define different test scenarios
class WebsiteUser(TenderExtractionUser):
    """Default user for general load testing."""

    pass


class StressTestUser(HighVolumeUser):
    """User for stress testing scenarios."""

    pass


class ConsistencyTestUser(APIConsistencyUser):
    """User for consistency and reliability testing."""

    pass
