#!/usr/bin/env python3
"""
Simple Qwen API proxy that adds OAuth token authentication.
"""

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

QWEN_API_BASE = "http://10.93.25.98:42005/v1"
QWEN_API_KEY = "my-secret-qwen-key"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{QWEN_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {QWEN_API_KEY}",
                "Content-Type": "application/json"
            },
            json=body
        )
        return JSONResponse(status_code=response.status_code, content=response.json())


@app.get("/v1/models")
async def models():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{QWEN_API_BASE}/models",
            headers={"Authorization": f"Bearer {QWEN_API_KEY}"}
        )
        return JSONResponse(status_code=response.status_code, content=response.json())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=42006)
