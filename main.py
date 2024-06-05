import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx

app = FastAPI()


class Message(BaseModel):
    role: str
    content: str


class OpenAIRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: Optional[bool] = False


class DuckDuckGoResponse(BaseModel):
    role: str
    message: str
    created: int
    id: str
    action: str
    model: str


@app.get("/")
async def read_root():
    return {
        "message": "Hello! Thank you for using PyFreeDuckDuckGo. Made by Victor Fu. Repo: https://github.com/victorfu/PyFreeDuckDuckGo"
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: OpenAIRequest):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Accept": "text/event-stream",
        "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://duckduckgo.com/",
        "Content-Type": "application/json",
        "Origin": "https://duckduckgo.com",
        "Connection": "keep-alive",
        "Cookie": "dcm=1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "TE": "trailers",
    }

    status_url = "https://duckduckgo.com/duckchat/v1/status"
    chat_url = "https://duckduckgo.com/duckchat/v1/chat"

    async with httpx.AsyncClient() as client:
        resp = await client.get(status_url, headers={"x-vqd-accept": "1", **headers})
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        vqd4 = resp.headers.get("x-vqd-4")

    payload = {
        "model": "gpt-3.5-turbo-0125",
        "messages": [message.dict() for message in request.messages],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            chat_url, json=payload, headers={"x-vqd-4": vqd4, **headers}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

    if not request.stream:
        result_content = ""
        id = ""
        created = 0
        model = ""
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                    id = data.get("id", "")
                    created = data.get("created", 0)
                    model = data.get("model", "")
                    result_content += data.get("message", "")
                except json.JSONDecodeError:
                    continue
        return {
            "id": id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result_content},
                    "finish_reason": "stop",
                }
            ],
        }

    async def event_stream():
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                chunk = line[6:]
                if chunk == "[DONE]":
                    yield f"data: {chunk}\n\n"
                    break
                try:
                    data = json.loads(chunk)
                    yield f"data: {json.dumps(data)}\n\n"
                except json.JSONDecodeError:
                    continue

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-3.5-turbo-0125",
                "object": "model",
                "created": 1692901427,
                "owned_by": "system",
            }
        ],
    }


# To run the app, use `uvicorn main:app --reload`
