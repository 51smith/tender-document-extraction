#!/usr/bin/env python3
"""
Start RQ worker with environment from .env file
"""
import os

# Avoid macOS forking issues
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

# Load environment from .env file (same as main app)
from dotenv import load_dotenv

load_dotenv()

import redis
from rq import Connection, Worker

from app.config import settings


def main():
    print("Starting RQ worker with configuration:")
    print(f"LLM_PROVIDER: {os.environ.get('LLM_PROVIDER')}")
    print(f"LLM_MODEL: {os.environ.get('LLM_MODEL')}")
    print(f"Settings provider: {settings.llm_provider}")
    print(f"Settings model: {settings.llm_model}")

    # Use Redis URL from environment (supports both Docker and local development)
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    print(f"Connecting to Redis: {redis_url}")
    redis_conn = redis.from_url(redis_url)

    with Connection(redis_conn):
        worker = Worker(["default", "high"], name="test-ollama-worker")
        print("Worker ready - listening for jobs...")
        worker.work()


if __name__ == "__main__":
    main()
