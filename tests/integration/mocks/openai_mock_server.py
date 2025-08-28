#!/usr/bin/env python3
"""Mock OpenAI API server for integration testing."""

import json
import random
import time
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="Mock OpenAI API", version="1.0.0")


class ChatCompletionMessage(BaseModel):
    """Chat completion message model."""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request model."""

    model: str
    messages: List[ChatCompletionMessage]
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    response_format: Optional[Dict[str, str]] = None


class ChatCompletionResponse(BaseModel):
    """OpenAI chat completion response model."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


# Mock responses for different scenarios
MOCK_EXTRACTION_RESPONSE = {
    "id": "chatcmpl-test123",
    "object": "chat.completion",
    "created": int(time.time()),
    "model": "gpt-4-turbo-preview",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "project_title": "Solar Panel Installation Project",
                        "estimated_value": 2500000.0,
                        "currency": "USD",
                        "submission_deadline": "2024-11-30T17:00:00Z",
                        "contracting_authority": {
                            "name": "Green Energy Department",
                            "contact": "contracts@greenenergy.gov",
                        },
                        "evaluation_criteria": [
                            {"name": "Technical Approach", "weight": 0.35},
                            {"name": "Cost", "weight": 0.35},
                            {"name": "Timeline", "weight": 0.15},
                            {"name": "Sustainability", "weight": 0.15},
                        ],
                        "confidence_scores": {
                            "project_title": 0.93,
                            "estimated_value": 0.87,
                            "submission_deadline": 0.89,
                            "contracting_authority": 0.92,
                            "evaluation_criteria": 0.88,
                        },
                        "extraction_metadata": {
                            "processing_time": 1.8,
                            "confidence_overall": 0.89,
                            "flags": ["multi_page_document"],
                        },
                    }
                ),
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 1150, "completion_tokens": 380, "total_tokens": 1530},
}

MOCK_ERROR_RESPONSES = {
    "rate_limit": {
        "error": {
            "message": "Rate limit reached for requests",
            "type": "requests",
            "param": None,
            "code": "rate_limit_exceeded",
        }
    },
    "quota_exceeded": {
        "error": {
            "message": "You exceeded your current quota, please check your plan and billing details.",
            "type": "insufficient_quota",
            "param": None,
            "code": "insufficient_quota",
        }
    },
    "invalid_request": {
        "error": {
            "message": "Invalid request format",
            "type": "invalid_request_error",
            "param": "messages",
            "code": None,
        }
    },
}


# State management for testing different scenarios
request_count = 0
failure_mode = None  # Can be: rate_limit, quota_exceeded, invalid_request, timeout
failure_probability = 0.0  # Probability of triggering failure (0.0-1.0)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-openai"}


@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest, authorization: str = Header(None)):
    """Mock OpenAI chat completions endpoint."""
    global request_count, failure_mode, failure_probability

    request_count += 1

    # Simulate API key validation
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail={"error": {"message": "Invalid API key provided"}}
        )

    # Simulate processing delay
    await asyncio.sleep(random.uniform(0.2, 0.8))

    # Check for configured failure scenarios
    if failure_mode and (failure_probability >= 1.0 or random.random() < failure_probability):
        if failure_mode == "rate_limit":
            raise HTTPException(status_code=429, detail=MOCK_ERROR_RESPONSES["rate_limit"])
        elif failure_mode == "quota_exceeded":
            raise HTTPException(status_code=429, detail=MOCK_ERROR_RESPONSES["quota_exceeded"])
        elif failure_mode == "invalid_request":
            raise HTTPException(status_code=400, detail=MOCK_ERROR_RESPONSES["invalid_request"])
        elif failure_mode == "timeout":
            await asyncio.sleep(30)  # Simulate timeout

    # Analyze request content to provide contextual responses
    prompt_content = ""
    for message in request.messages:
        prompt_content += message.content

    # Return different responses based on model and content
    response = MOCK_EXTRACTION_RESPONSE.copy()
    response["model"] = request.model
    response["created"] = int(time.time())

    if "gpt-3.5" in request.model:
        # Simulate faster, cheaper model
        response["usage"]["prompt_tokens"] = int(response["usage"]["prompt_tokens"] * 0.7)
        response["usage"]["completion_tokens"] = int(response["usage"]["completion_tokens"] * 0.8)
        response["usage"]["total_tokens"] = (
            response["usage"]["prompt_tokens"] + response["usage"]["completion_tokens"]
        )
        await asyncio.sleep(0.1)
    elif "batch" in prompt_content.lower():
        # Simulate batch processing response
        response["usage"]["total_tokens"] = random.randint(3000, 8000)
    elif "error" in prompt_content.lower():
        # Trigger error for testing
        raise HTTPException(status_code=400, detail=MOCK_ERROR_RESPONSES["invalid_request"])

    return response


@app.get("/v1/models")
async def list_models(authorization: str = Header(None)):
    """Mock OpenAI models endpoint."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail={"error": {"message": "Invalid API key provided"}}
        )

    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-4-turbo-preview",
                "object": "model",
                "created": 1677610602,
                "owned_by": "openai",
            },
            {"id": "gpt-3.5-turbo", "object": "model", "created": 1677649963, "owned_by": "openai"},
        ],
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


@app.get("/test-control/stats")
async def get_stats():
    """Get mock server statistics."""
    return {
        "request_count": request_count,
        "failure_mode": failure_mode,
        "failure_probability": failure_probability,
    }


if __name__ == "__main__":
    import asyncio

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
