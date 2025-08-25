#!/usr/bin/env python3
"""
RQ Worker startup script for local development.

This script starts RQ workers to process background jobs.
In production, workers should be started via Docker or process managers.
"""

import os
import logging
import sys
from pathlib import Path

# Fix for macOS fork() issue with RQ workers
os.environ.setdefault('OBJC_DISABLE_INITIALIZE_FORK_SAFETY', 'YES')

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from rq import Worker, SimpleWorker
import redis as redis_sync
from app.config import settings
from app.services.extraction_worker import process_extraction_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Start RQ worker process."""
    
    print("🔧 Starting RQ Worker for Tender Document Extraction...")
    print(f"📡 Redis URL: {settings.redis_url}")
    
    # Connect to Redis (synchronous connection for RQ)
    try:
        connection = redis_sync.from_url(settings.redis_url)
        connection.ping()  # Test connection
        print("✅ Connected to Redis successfully")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        print("💡 Make sure Redis is running: brew install redis && redis-server")
        sys.exit(1)
    
    # Create worker for both default and high priority queues
    try:
        # Use SimpleWorker on macOS to avoid fork issues
        import platform
        if platform.system() == 'Darwin':  # macOS
            print("🍎 macOS detected - using SimpleWorker (no forking)")
            worker = SimpleWorker(
                ['high', 'default'],  # Process high priority first, then default
                connection=connection,
                name=f'worker-{settings.environment}'
            )
        else:
            worker = Worker(
                ['high', 'default'],  # Process high priority first, then default
                connection=connection,
                name=f'worker-{settings.environment}'
            )
        
        print("🚀 Worker started successfully!")
        print("📋 Listening to queues: ['high', 'default']")
        print("⏹️  Press Ctrl+C to stop")
        
        # Start worker (SimpleWorker doesn't support scheduler)
        if isinstance(worker, SimpleWorker):
            worker.work()
        else:
            worker.work(with_scheduler=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()