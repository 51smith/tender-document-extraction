"""
Test script to verify all LLM backends are working correctly.
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath('.'))

from app.config import settings
from app.services.llm_service import LLMServiceFactory


async def test_llm_backend(provider: str, model: str):
    """Test a specific LLM backend."""
    print(f"\n🔍 Testing {provider} with model {model}")
    
    # Update settings temporarily
    original_provider = settings.llm_provider
    original_model = settings.llm_model
    
    settings.llm_provider = provider
    settings.llm_model = model
    
    try:
        # Create LLM service
        llm_service = LLMServiceFactory.create_llm_service()
        
        # Test health check
        print("  ✓ Health check...", end=" ")
        health = await llm_service.health_check()
        if health:
            print("PASSED")
        else:
            print("FAILED")
            return False
        
        # Test simple extraction
        print("  ✓ Simple extraction...", end=" ")
        result = await llm_service.generate_content(
            prompt="Extract project title from: 'Project XYZ - Software Development Contract'. Respond with JSON format: {\"project_title\": \"...\"}",
            json_schema={"type": "object", "properties": {"project_title": {"type": "string"}}}
        )
        
        if "project_title" in str(result):
            print("PASSED")
            print(f"    Result: {result}")
        else:
            print("FAILED")
            print(f"    Result: {result}")
            return False
            
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        # Restore original settings
        settings.llm_provider = original_provider
        settings.llm_model = original_model


async def main():
    """Main test function."""
    print("🚀 Testing Multi-LLM Backend Support")
    print("=" * 50)
    
    results = {}
    
    # Test Ollama (local)
    results["ollama"] = await test_llm_backend("ollama", "llama3:latest")
    
    # Test Gemini (if API key available)
    if settings.google_api_key:
        results["gemini-pro"] = await test_llm_backend("gemini", "gemini-2.5-pro")
        results["gemini-flash"] = await test_llm_backend("gemini", "gemini-1.5-flash")
    else:
        print("\n⚠️  Skipping Gemini tests (no API key)")
    
    # Test OpenAI (if API key available)  
    if hasattr(settings, 'openai_api_key') and settings.openai_api_key:
        results["openai"] = await test_llm_backend("openai", "gpt-4o-mini")
    else:
        print("\n⚠️  Skipping OpenAI tests (no API key)")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    for backend, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {backend:20} {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests and total_tests > 0:
        print("🎉 All available backends are working!")
    elif passed_tests > 0:
        print("⚠️  Some backends are working, others may need configuration")
    else:
        print("❌ No backends are working - check configuration")


if __name__ == "__main__":
    asyncio.run(main())