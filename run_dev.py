#!/usr/bin/env python3
"""
Development server runner for the Tender Document Extraction Service.
"""

import uvicorn
import os
from pathlib import Path

if __name__ == "__main__":
    # Ensure we're in the right directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Load environment variables from .env if it exists
    env_file = project_root / ".env"
    if not env_file.exists():
        print("⚠️  .env file not found. Copy .env.example to .env and configure your settings.")
        print("Example: cp .env.example .env")
        exit(1)
    
    print("🚀 Starting Tender Document Extraction Service in development mode...")
    print("📝 API documentation will be available at: http://localhost:8000/docs")
    print("🏥 Health check available at: http://localhost:8000/health")
    print("📊 Detailed health check at: http://localhost:8000/health/detailed")
    
    # Run the development server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app", "prompts"],
        log_level="info",
        access_log=True
    )