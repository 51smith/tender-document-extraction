#!/usr/bin/env python3
"""Mock Ollama API server for integration testing."""

import json
import time
import random
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn


app = FastAPI(title="Mock Ollama API", version="1.0.0")


class GenerateRequest(BaseModel):
    """Ollama generate request model."""
    model: str
    prompt: str
    stream: Optional[bool] = False
    format: Optional[str] = None
    options: Optional[Dict[str, Any]] = {}


class GenerateResponse(BaseModel):
    """Ollama generate response model."""
    model: str
    created_at: str
    response: str
    done: bool
    context: Optional[List[int]] = []
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None


# Mock responses for different scenarios
MOCK_EXTRACTION_RESPONSE = json.dumps({
    "project_title": "Infrastructure Upgrade Project B2",
    "estimated_value": 3750000.0,
    "currency": "EUR",
    "submission_deadline": "2024-10-20T16:00:00Z",
    "contracting_authority": {
        "name": "Municipal Infrastructure Department", 
        "contact": "tenders@municipality.org"
    },
    "evaluation_criteria": [
        {"name": "Technical Solution", "weight": 0.45},
        {"name": "Price Competitiveness", "weight": 0.35},
        {"name": "Project Timeline", "weight": 0.20}
    ],
    "confidence_scores": {
        "project_title": 0.91,
        "estimated_value": 0.85,
        "submission_deadline": 0.94,
        "contracting_authority": 0.89,
        "evaluation_criteria": 0.82
    },
    "extraction_metadata": {
        "processing_time": 3.1,
        "confidence_overall": 0.88,
        "flags": ["complex_formatting", "multiple_sections"]
    }
})


# State management for testing different scenarios
request_count = 0
failure_mode = None  # Can be: connection_error, model_not_found, timeout, generation_error
failure_probability = 0.0
available_models = ["llama3.3:latest", "llama3:latest", "gemma2:9b", "mistral:latest"]


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-ollama"}


@app.get("/api/tags")
async def list_models():
    """Mock Ollama list models endpoint."""
    global failure_mode, failure_probability
    
    if failure_mode == "connection_error" and random.random() < failure_probability:
        raise HTTPException(status_code=503, detail="Connection to Ollama server failed")
    
    return {
        "models": [
            {
                "name": model,
                "modified_at": "2024-01-15T10:30:00Z",
                "size": random.randint(2000000000, 8000000000),
                "digest": f"sha256:{'a' * 64}",
                "details": {
                    "format": "gguf",
                    "family": "llama" if "llama" in model else "gemma" if "gemma" in model else "mistral",
                    "families": [],
                    "parameter_size": "7B" if "7b" in model else "9B" if "9b" in model else "8x7B"
                }
            }
            for model in available_models
        ]
    }


@app.post("/api/generate")
async def generate(request: GenerateRequest):
    """Mock Ollama generate endpoint."""
    global request_count, failure_mode, failure_probability
    
    request_count += 1
    
    # Check if model exists
    if request.model not in available_models:
        raise HTTPException(
            status_code=404,
            detail=f"model '{request.model}' not found, try pulling it first"
        )
    
    # Simulate processing delay based on model size
    if "7b" in request.model or "9b" in request.model:
        delay = random.uniform(1.0, 3.0)
    else:
        delay = random.uniform(2.0, 5.0)
    
    await asyncio.sleep(delay * 0.1)  # Scale down for testing
    
    # Check for configured failure scenarios
    if failure_mode and (failure_probability >= 1.0 or random.random() < failure_probability):
        if failure_mode == "connection_error":
            raise HTTPException(status_code=503, detail="Failed to connect to Ollama")
        elif failure_mode == "model_not_found":
            raise HTTPException(status_code=404, detail=f"model '{request.model}' not found")
        elif failure_mode == "generation_error":
            raise HTTPException(status_code=500, detail="Generation failed due to internal error")
        elif failure_mode == "timeout":
            await asyncio.sleep(30)  # Simulate timeout
    
    # Analyze prompt content to provide contextual responses
    prompt_content = request.prompt.lower()
    
    # Determine response based on prompt
    if "json" in prompt_content and ("extract" in prompt_content or "tender" in prompt_content):
        response_text = MOCK_EXTRACTION_RESPONSE
    elif "error" in prompt_content:
        raise HTTPException(status_code=500, detail="Simulated generation error")
    elif "batch" in prompt_content:
        # Simulate batch response with multiple items
        batch_response = {
            "documents": [
                json.loads(MOCK_EXTRACTION_RESPONSE),
                {**json.loads(MOCK_EXTRACTION_RESPONSE), "project_title": "Additional Project C3"}
            ]
        }
        response_text = json.dumps(batch_response)
    else:
        response_text = MOCK_EXTRACTION_RESPONSE
    
    # Calculate mock timing metrics
    total_duration = int(delay * 1_000_000_000)  # Convert to nanoseconds
    prompt_tokens = len(request.prompt.split())
    response_tokens = len(response_text.split())
    
    return {
        "model": request.model,
        "created_at": "2024-01-15T10:30:00Z",
        "response": response_text,
        "done": True,
        "context": list(range(100)),  # Mock context tokens
        "total_duration": total_duration,
        "load_duration": int(total_duration * 0.1),
        "prompt_eval_count": prompt_tokens,
        "prompt_eval_duration": int(total_duration * 0.3),
        "eval_count": response_tokens,
        "eval_duration": int(total_duration * 0.6)
    }


@app.post("/api/pull")
async def pull_model(request: Request):
    """Mock Ollama pull model endpoint."""
    body = await request.json()
    model_name = body.get("name", "")
    
    if not model_name:
        raise HTTPException(status_code=400, detail="model name is required")
    
    # Simulate pull process (normally streaming)
    await asyncio.sleep(0.5)
    
    return {
        "status": "success",
        "digest": f"sha256:{'b' * 64}",
        "total": 4000000000
    }


@app.get("/api/show")
async def show_model(name: str):
    """Mock Ollama show model endpoint."""
    if name not in available_models:
        raise HTTPException(status_code=404, detail=f"model '{name}' not found")
    
    return {
        "license": "Apache License 2.0",
        "modelfile": f"FROM {name}",
        "parameters": "temperature 0.7\ntop_p 0.9",
        "template": "{{ .Prompt }}",
        "details": {
            "format": "gguf",
            "family": "llama" if "llama" in name else "gemma" if "gemma" in name else "mistral",
            "parameter_size": "7B"
        }
    }


# Test control endpoints
@app.post("/test-control/set-failure-mode")
async def set_failure_mode(request: Request):
    """Set failure mode for testing."""
    global failure_mode, failure_probability
    body = await request.json()
    failure_mode = body.get("mode")
    failure_probability = body.get("probability", 0.0)
    return {"message": f"Failure mode set to {failure_mode} with probability {failure_probability}"}


@app.post("/test-control/reset")
async def reset_state():
    """Reset mock server state."""
    global request_count, failure_mode, failure_probability
    request_count = 0
    failure_mode = None
    failure_probability = 0.0
    return {"message": "State reset"}


@app.post("/test-control/add-model")
async def add_model(request: Request):
    """Add model for testing."""
    global available_models
    body = await request.json()
    model_name = body.get("name")
    if model_name and model_name not in available_models:
        available_models.append(model_name)
    return {"message": f"Added model {model_name}"}


@app.post("/test-control/remove-model")
async def remove_model(request: Request):
    """Remove model for testing."""
    global available_models
    body = await request.json()
    model_name = body.get("name")
    if model_name in available_models:
        available_models.remove(model_name)
    return {"message": f"Removed model {model_name}"}


@app.get("/test-control/stats")
async def get_stats():
    """Get mock server statistics."""
    return {
        "request_count": request_count,
        "failure_mode": failure_mode,
        "failure_probability": failure_probability,
        "available_models": available_models
    }


if __name__ == "__main__":
    import asyncio
    uvicorn.run(app, host="0.0.0.0", port=11434, log_level="info")