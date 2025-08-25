#!/usr/bin/env python3
"""
Comprehensive queue testing script.

This script tests the complete queue workflow:
1. Job creation and storage
2. Worker processing 
3. Job status updates
4. Job completion/failure
5. Job deletion/cancellation

Usage:
    python test_queue.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
import redis as redis_sync
from app.config import settings

BASE_URL = "http://localhost:8000"

def print_status(message, emoji="ℹ️"):
    print(f"{emoji} {message}")

def print_success(message):
    print_status(message, "✅")

def print_error(message):
    print_status(message, "❌")

def print_warning(message):
    print_status(message, "⚠️")

def create_test_file():
    """Create a test file for API testing."""
    test_content = """
    TENDER NOTIFICATION
    
    Project: AI Document Processing System
    Authority: Tech Solutions Ltd
    Deadline: 2024-12-31
    Value: €50,000
    
    Requirements:
    - Natural language processing
    - Document extraction
    - API development
    
    Please submit proposals by the deadline.
    """
    
    test_file = "/tmp/test_tender_doc.txt"
    with open(test_file, "w") as f:
        f.write(test_content)
    return test_file

def test_server_health():
    """Test if the server is running and healthy."""
    print_status("Testing server health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("Server is healthy")
            return True
        else:
            print_error(f"Server unhealthy: {response.status_code}")
            return False
    except requests.RequestException as e:
        print_error(f"Server not reachable: {e}")
        return False

def test_redis_connection():
    """Test Redis connection."""
    print_status("Testing Redis connection...")
    try:
        client = redis_sync.from_url(settings.redis_url)
        client.ping()
        print_success("Redis connection successful")
        return True
    except Exception as e:
        print_error(f"Redis connection failed: {e}")
        return False

def submit_test_job():
    """Submit a test job and return job ID."""
    print_status("Submitting test job...")
    
    test_file = create_test_file()
    
    try:
        with open(test_file, "rb") as f:
            files = {"files": (f"test_tender_doc.txt", f, "text/plain")}
            data = {"config_name": "default", "enable_multimodal": "true"}
            
            response = requests.post(
                f"{BASE_URL}/api/v1/extract/batch",
                files=files,
                data=data,
                timeout=30
            )
            
        if response.status_code == 200:
            result = response.json()
            job_id = result.get("job_id")
            print_success(f"Job submitted successfully: {job_id}")
            return job_id
        else:
            print_error(f"Job submission failed: {response.status_code} - {response.text}")
            return None
            
    except requests.RequestException as e:
        print_error(f"Job submission error: {e}")
        return None

def monitor_job(job_id, timeout=60):
    """Monitor job progress and return final status."""
    print_status(f"Monitoring job: {job_id}")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}")
            
            if response.status_code == 200:
                job_data = response.json()
                status = job_data.get("status")
                progress = job_data.get("progress", 0)
                
                if status != last_status:
                    print_status(f"Job {job_id}: {status} ({progress:.1f}%)")
                    last_status = status
                
                if status in ["completed", "failed", "cancelled"]:
                    return job_data
                    
            else:
                print_warning(f"Failed to get job status: {response.status_code}")
                
        except requests.RequestException as e:
            print_warning(f"Error checking job status: {e}")
            
        time.sleep(2)
    
    print_error(f"Job monitoring timed out after {timeout}s")
    return None

def perform_job_deletion_test(job_id):
    """Test job deletion functionality."""
    print_status(f"Testing job deletion: {job_id}")
    
    try:
        # Test cancellation (force=false)
        response = requests.delete(f"{BASE_URL}/api/v1/jobs/{job_id}")
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"Job cancellation: {result['message']}")
            
            # Test permanent deletion (force=true)
            response = requests.delete(f"{BASE_URL}/api/v1/jobs/{job_id}?force=true")
            
            if response.status_code == 200:
                result = response.json()
                print_success(f"Job deletion: {result['message']}")
                return True
            else:
                print_error(f"Job deletion failed: {response.status_code}")
                return False
                
        else:
            print_error(f"Job cancellation failed: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print_error(f"Job deletion error: {e}")
        return False

def test_queue_statistics():
    """Test queue statistics endpoint."""
    print_status("Testing queue statistics...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/statistics")
        
        if response.status_code == 200:
            stats = response.json()
            print_success("Queue statistics:")
            print(f"  Total jobs: {stats.get('total_jobs', 'N/A')}")
            print(f"  Queue stats: {stats.get('queue_stats', 'N/A')}")
            print(f"  Status counts: {stats.get('status_counts', 'N/A')}")
            return True
        else:
            print_error(f"Statistics request failed: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print_error(f"Statistics error: {e}")
        return False

def check_worker_running():
    """Check if RQ worker is running."""
    print_status("Checking if RQ worker is running...")
    
    try:
        client = redis_sync.from_url(settings.redis_url)
        
        # Check active workers
        from rq import Worker
        workers = Worker.all(connection=client)
        
        if workers:
            print_success(f"Found {len(workers)} active workers:")
            for worker in workers:
                print(f"  - {worker.name}: {worker.get_state()}")
            return True
        else:
            print_error("No RQ workers found!")
            print_warning("Start a worker with: python run_worker.py")
            return False
            
    except Exception as e:
        print_error(f"Worker check failed: {e}")
        return False

def main():
    """Run comprehensive queue tests."""
    print("🧪 Starting Comprehensive Queue Testing")
    print("=" * 50)
    
    # Pre-flight checks
    if not test_server_health():
        print_error("Server not available. Start with: python run_dev.py")
        sys.exit(1)
    
    if not test_redis_connection():
        print_error("Redis not available. Start with: redis-server")
        sys.exit(1)
    
    worker_running = check_worker_running()
    
    # Test queue statistics
    test_queue_statistics()
    
    # Test job submission
    job_id = submit_test_job()
    if not job_id:
        sys.exit(1)
    
    if worker_running:
        # Monitor job processing
        print_status("Worker is running - monitoring job processing...")
        final_job_data = monitor_job(job_id, timeout=120)
        
        if final_job_data:
            status = final_job_data.get("status")
            if status == "completed":
                print_success("✅ Job completed successfully!")
                
                # Check results
                result = final_job_data.get("result")
                if result:
                    print_success("Job produced results:")
                    if isinstance(result, list) and result:
                        first_result = result[0]
                        if isinstance(first_result, dict):
                            extracted_data = first_result.get("extracted_data", {})
                            project_title = extracted_data.get("project_title", "N/A")
                            print(f"  Project Title: {project_title}")
                else:
                    print_warning("Job completed but no results found")
                    
            elif status == "failed":
                print_error("Job failed to complete")
                error = final_job_data.get("error_message", "Unknown error")
                print(f"  Error: {error}")
            else:
                print_warning(f"Job ended with status: {status}")
        else:
            print_error("Job monitoring failed")
    else:
        print_warning("No worker running - job will remain pending")
        print_status("Checking job was queued properly...")
        time.sleep(5)  # Give it time to be stored
        
        # Check job exists and is pending
        try:
            response = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}")
            if response.status_code == 200:
                job_data = response.json()
                if job_data.get("status") == "pending":
                    print_success("Job is properly queued as pending")
                else:
                    print_error(f"Job status is {job_data.get('status')}, expected pending")
            else:
                print_error("Failed to retrieve job after submission")
        except Exception as e:
            print_error(f"Failed to check job status: {e}")
    
    # Test job deletion
    print_status("\nTesting job management...")
    if perform_job_deletion_test(job_id):
        print_success("Job deletion works correctly")
    
    # Final statistics
    print_status("\nFinal queue statistics:")
    test_queue_statistics()
    
    print("\n🎉 Queue testing completed!")
    
    if not worker_running:
        print_warning("\n💡 To test actual job processing:")
        print("   1. Start a worker: python run_worker.py")
        print("   2. Run this test again")
        print("   3. Or use: make run-all")

if __name__ == "__main__":
    main()