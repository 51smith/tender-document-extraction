#!/usr/bin/env python3
"""
Test script to start an RQ worker with proper environment
"""
import os
import sys

import redis
from rq import Connection, Worker

# Add app directory to Python path
sys.path.insert(0, "/Users/shanesmith/Documents/development/tender_batch_extract")

# Set environment variables explicitly
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["LLM_MODEL"] = "llama3:latest"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

# Import after setting environment
from app.config import settings


def main():
    print("Starting RQ worker with:")
    print(f"LLM_PROVIDER: {os.environ.get('LLM_PROVIDER')}")
    print(f"LLM_MODEL: {os.environ.get('LLM_MODEL')}")
    print(f"Settings LLM provider: {settings.llm_provider}")
    print(f"Settings LLM model: {settings.llm_model}")

    # Connect to Redis
    redis_conn = redis.from_url("redis://localhost:6379/0")

    with Connection(redis_conn):
        worker = Worker(["default", "high"], name="test-worker")
        print("Starting RQ worker...")
        worker.work(burst=False)


if __name__ == "__main__":
    main()
