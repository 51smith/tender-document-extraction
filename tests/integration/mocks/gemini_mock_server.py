#!/usr/bin/env python3
"""Mock Gemini API server for integration testing."""

import json
import random


import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="Mock Gemini API", version="1.0.0")


class GenerateContentRequest(BaseModel):
    """Gemini generate content request model."""



class GenerateContentResponse(BaseModel):
    """Gemini generate content response model."""



# Mock responses for different scenarios
MOCK_EXTRACTION_RESPONSE = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "project_title": "Highway Construction Project A1",
                                "estimated_value": 5000000.0,
                                "currency": "EUR",
                                "submission_deadline": "2024-12-15T23:59:59Z",
                                "contracting_authority": {
                                    "name": "Department of Transportation",
                                    "contact": "procurement@dot.gov",
                                },
                                "evaluation_criteria": [
                                    {"name": "Technical Capability", "weight": 0.4},
                                    {"name": "Price", "weight": 0.4},
                                    {"name": "Experience", "weight": 0.2},
                                ],
                                "confidence_scores": {
                                    "project_title": 0.95,
                                    "estimated_value": 0.88,
                                    "submission_deadline": 0.92,
                                    "contracting_authority": 0.91,
                                    "evaluation_criteria": 0.85,
                                },
                                "extraction_metadata": {
                                    "processing_time": 2.3,
                                    "confidence_overall": 0.90,
                                    "flags": [],
                                },
                            }
                        )
                    }
                ]
            },
            "finishReason": "STOP",
            "safetyRatings": [
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "probability": "NEGLIGIBLE"}
            ],
        }
    ],
    "usageMetadata": {
        "promptTokenCount": 1247,
        "candidatesTokenCount": 423,
        "totalTokenCount": 1670,
    },
}

MOCK_ERROR_RESPONSES = {
    "rate_limit": {
        "error": {
            "code": 429,
            "message": "Quota exceeded for requests per minute per user.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "RATE_LIMIT_EXCEEDED",
                    "domain": "googleapis.com",
                }
            ],
        }
    },
    "quota_exceeded": {
        "error": {
            "code": 429,
            "message": "Quota exceeded for requests per day.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "QUOTA_EXCEEDED",
                    "domain": "googleapis.com",
                }
            ],
        }
    },
    "safety_filter": {
        "candidates": [
            {
                "finishReason": "SAFETY",
                "safetyRatings": [
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "probability": "HIGH",
                        "blocked": True,
                    }
                ],
            }
        ],
        "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 0, "totalTokenCount": 50},
    },
}


# State management for testing different scenarios
request_count = 0
failure_mode = None  # Can be: rate_limit, quota_exceeded, safety_filter, network_error
failure_probability = 0.0  # Probability of triggering failure (0.0-1.0)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-gemini"}


@app.post("/v1beta/models/gemini-2.5-pro:generateContent")
async def generate_content(
    request: GenerateContentRequest, x_goog_api_key: str = Header(None, alias="x-goog-api-key")
):
    """Mock Gemini generateContent endpoint."""
    global request_count, failure_mode, failure_probability

    request_count += 1

    # Simulate API key validation
    if not x_goog_api_key or x_goog_api_key == "invalid-key":
        raise HTTPException(
            status_code=401, detail={"error": {"code": 401, "message": "Invalid API key"}}
        )

    # Simulate processing delay
    await asyncio.sleep(random.uniform(0.1, 0.5))

    # Check for configured failure scenarios
    if failure_mode and (failure_probability >= 1.0 or random.random() < failure_probability):
        if failure_mode == "rate_limit":
            raise HTTPException(status_code=429, detail=MOCK_ERROR_RESPONSES["rate_limit"])
        elif failure_mode == "quota_exceeded":
            raise HTTPException(status_code=429, detail=MOCK_ERROR_RESPONSES["quota_exceeded"])
        elif failure_mode == "safety_filter":
            return MOCK_ERROR_RESPONSES["safety_filter"]
        elif failure_mode == "network_error":
            raise HTTPException(
                status_code=503, detail={"error": {"message": "Service temporarily unavailable"}}
            )

    # Analyze request content to provide contextual responses
    prompt_text = ""
    if request.contents:
        for content in request.contents:
            if "parts" in content:
                for part in content["parts"]:
                    if "text" in part:
                        prompt_text += part["text"]

    # Return different responses based on prompt content
    if "batch" in prompt_text.lower():
        # Simulate batch processing response
        response = MOCK_EXTRACTION_RESPONSE.copy()
        response["usageMetadata"]["totalTokenCount"] = random.randint(2000, 5000)
        return response
    elif "error" in prompt_text.lower():
        # Trigger error for testing
        raise HTTPException(
            status_code=400, detail={"error": {"message": "Invalid request format"}}
        )
    else:
        # Standard extraction response
        return MOCK_EXTRACTION_RESPONSE


@app.post("/v1beta/models/gemini-2.5-flash:generateContent")
async def generate_content_flash(
    request: GenerateContentRequest, x_goog_api_key: str = Header(None, alias="x-goog-api-key")
):
    """Mock Gemini Flash generateContent endpoint."""
    # Faster response with lower token usage
    response = MOCK_EXTRACTION_RESPONSE.copy()
    response["usageMetadata"] = {
        "promptTokenCount": 500,
        "candidatesTokenCount": 200,
        "totalTokenCount": 700,
    }
    await asyncio.sleep(random.uniform(0.05, 0.2))
    return response


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
