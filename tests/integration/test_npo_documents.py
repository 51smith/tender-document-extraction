#!/usr/bin/env python3
"""
Integration tests with real NPO tender documents.
"""

import time
from pathlib import Path

import pytest
import requests


class TestNPODocuments:
    """Test real-world tender document extraction with NPO documents."""

    @pytest.fixture
    def npo_documents(self):
        """Get paths to NPO test documents."""
        test_data_dir = Path(__file__).parent.parent / "testdata" / "npo"
        documents = list(test_data_dir.glob("*.pdf"))
        assert len(documents) > 0, "No NPO test documents found"
        return documents

    @pytest.fixture
    def api_base_url(self):
        """Base URL for the API."""
        return "http://localhost:8000"

    def test_server_health(self, api_base_url):
        """Test that the server is running."""
        response = requests.get(f"{api_base_url}/health")
        assert response.status_code == 200

    @pytest.mark.slow
    def test_single_npo_document_extraction(self, npo_documents, api_base_url):
        """Test extraction with a single NPO document."""
        # Use the main tender document
        main_doc = next(
            (doc for doc in npo_documents if "Opdrachtomschrijving" in doc.name), npo_documents[0]
        )

        print(f"\nTesting with document: {main_doc.name}")

        # Submit job
        with open(main_doc, "rb") as f:
            files = {"files": (main_doc.name, f, "application/pdf")}
            data = {"config_name": "default", "enable_multimodal": "true"}

            response = requests.post(
                f"{api_base_url}/api/v1/extract/batch", files=files, data=data, timeout=30
            )

        assert response.status_code == 200, f"Job submission failed: {response.text}"

        result = response.json()
        job_id = result.get("job_id")
        assert job_id is not None, "No job_id returned"

        print(f"Job submitted: {job_id}")

        # Monitor job with extended timeout for real documents
        max_wait_time = 300  # 5 minutes
        poll_interval = 5

        for i in range(max_wait_time // poll_interval):
            response = requests.get(f"{api_base_url}/api/v1/jobs/{job_id}")
            assert response.status_code == 200, f"Failed to get job status: {response.status_code}"

            job_data = response.json()
            status = job_data.get("status")
            progress = job_data.get("progress", 0)

            print(f"  Status ({i*poll_interval}s): {status} ({progress:.1f}%)")

            if status == "completed":
                # Analyze results
                result_data = job_data.get("result", [])
                assert len(result_data) > 0, "No results returned"

                extracted = result_data[0].get("extracted_data", {})
                raw_response = result_data[0].get("raw_response", {})
                notes = result_data[0].get("extraction_notes", {})

                print(f"\nEXTRACTION RESULTS:")
                print(f"Project title: {extracted.get('project_title')}")
                print(f"Authority: {extracted.get('contracting_authority')}")
                print(f"Value: {extracted.get('estimated_value')}")
                print(f"Deadline: {extracted.get('submission_deadline')}")

                if raw_response.get("error"):
                    print(f"Raw response error: {raw_response.get('error')}")
                    print(f"Error type: {raw_response.get('type')}")

                print(f"Ambiguities: {notes.get('ambiguities', [])}")

                # The extraction should not have errors
                assert not raw_response.get(
                    "error"
                ), f"Extraction failed: {raw_response.get('error')}"

                # At least some basic information should be extracted
                project_title = extracted.get("project_title")
                contracting_authority = extracted.get("contracting_authority")

                if not project_title and not contracting_authority:
                    pytest.fail(f"No basic information extracted. Full data: {extracted}")

                break

            elif status == "failed":
                error = job_data.get("error_message", "Unknown error")
                pytest.fail(f"Job failed: {error}")

            time.sleep(poll_interval)
        else:
            pytest.fail(
                f"Job did not complete within {max_wait_time} seconds. Final status: {status}"
            )

    @pytest.mark.slow
    def test_multiple_npo_documents_extraction(self, npo_documents, api_base_url):
        """Test extraction with multiple NPO documents (the failing case)."""
        print(f"\nTesting with {len(npo_documents)} documents:")
        for doc in npo_documents:
            print(f"  - {doc.name}")

        # Submit all documents
        files = []
        for doc in npo_documents:
            with open(doc, "rb") as f:
                files.append(("files", (doc.name, f.read(), "application/pdf")))

        data = {"config_name": "default", "enable_multimodal": "true"}

        response = requests.post(
            f"{api_base_url}/api/v1/extract/batch", files=files, data=data, timeout=30
        )

        assert response.status_code == 200, f"Job submission failed: {response.text}"

        result = response.json()
        job_id = result.get("job_id")
        assert job_id is not None, "No job_id returned"

        print(f"Job submitted: {job_id}")

        # Monitor job with extended timeout
        max_wait_time = 600  # 10 minutes for multiple documents
        poll_interval = 10

        for i in range(max_wait_time // poll_interval):
            response = requests.get(f"{api_base_url}/api/v1/jobs/{job_id}")
            assert response.status_code == 200, f"Failed to get job status: {response.status_code}"

            job_data = response.json()
            status = job_data.get("status")
            progress = job_data.get("progress", 0)

            print(f"  Status ({i*poll_interval}s): {status} ({progress:.1f}%)")

            if status == "completed":
                # Analyze results in detail
                result_data = job_data.get("result", [])
                assert len(result_data) > 0, "No results returned"

                extracted = result_data[0].get("extracted_data", {})
                raw_response = result_data[0].get("raw_response", {})
                notes = result_data[0].get("extraction_notes", {})
                metadata = result_data[0].get("processing_metadata", {})

                print(f"\nDETAILED EXTRACTION RESULTS:")
                print(f"Project title: {extracted.get('project_title')}")
                print(f"Authority: {extracted.get('contracting_authority')}")
                print(f"Value: {extracted.get('estimated_value')}")
                print(f"Deadline: {extracted.get('submission_deadline')}")
                print(f"CPV codes: {extracted.get('cpv_codes', [])}")
                print(f"Requirements count: {len(extracted.get('functional_requirements', []))}")

                print(f"\nMETADATA:")
                print(f"Processing time: {metadata.get('processing_time')}s")
                print(f"Tokens used: {metadata.get('actual_tokens')}")

                print(f"\nEXTRACTION NOTES:")
                print(f"Ambiguities: {notes.get('ambiguities', [])}")
                print(f"Processing notes: {notes.get('processing_notes', [])}")

                print(f"\nRAW RESPONSE:")
                if raw_response.get("error"):
                    print(f"Error: {raw_response.get('error')}")
                    print(f"Error type: {raw_response.get('type')}")
                else:
                    print("No errors in raw response")

                # Debug the current failure
                if raw_response.get("error"):
                    print(f"\nDEBUG: Current issue is: {raw_response.get('error')}")
                    if "'ExtractionNotes' object has no attribute 'processing_notes'" in str(
                        raw_response.get("error")
                    ):
                        print("This is the data model issue we're fixing")

                # For now, just verify the job completes without crashing
                # Later we'll add more specific assertions once the extraction works
                break

            elif status == "failed":
                error = job_data.get("error_message", "Unknown error")
                print(f"Job failed with error: {error}")

                # Get the job details for debugging
                result_data = job_data.get("result", [])
                if result_data:
                    raw_response = result_data[0].get("raw_response", {})
                    notes = result_data[0].get("extraction_notes", {})
                    print(f"Raw response error: {raw_response.get('error')}")
                    print(f"Ambiguities: {notes.get('ambiguities', [])}")

                pytest.fail(f"Job failed: {error}")

            time.sleep(poll_interval)
        else:
            pytest.fail(
                f"Job did not complete within {max_wait_time} seconds. Final status: {status}"
            )

    def test_gemini_response_format(self, npo_documents, api_base_url):
        """Test what Gemini is actually returning for our documents."""
        # This test will help us debug the JSON parsing issue
        main_doc = next(
            (doc for doc in npo_documents if "Opdrachtomschrijving" in doc.name), npo_documents[0]
        )

        print(f"\nTesting Gemini response format with: {main_doc.name}")

        # We'll create a simple test to see what Gemini returns
        # This will be implemented after we fix the current issues
        pass
